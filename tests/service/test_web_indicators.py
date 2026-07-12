"""tests/service/test_web_indicators.py — TDD for `GET /api/runs/{run_id}/indicators`
(REVIEW Trade View EMA/SAR overlays, spec
docs/superpowers/specs/2026-07-09-trade-view-indicator-overlays-design.md).

Parity is normative: the endpoint must compute indicators with the exact
params the run used (params_hash -> param_set, falling back to
variant.params_delta merged over EMASAR_DEFAULTS), via the SAME
`emasar.py` functions the strategy itself calls — never a re-ported/JS
version. Uses a throwaway `ResearchRegistry` (tmp_path db) + a small
synthetic lake, same pattern as tests/service/test_manage_api.py — never
touches the real `data/research.db` / `data/lake`.
"""
from __future__ import annotations

import math

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from sentinel_engine.research.registry2 import ResearchRegistry
from sentinel_engine.service.app import create_app
from sentinel_engine.strategies.emasar import _DEFAULT_PARAMS, ema_series, sar_series
from tests.golden.fake_feed import FakeFeed


@pytest.fixture
def registry(tmp_path):
    return ResearchRegistry(tmp_path / "research.db")


def _mk_synthetic_lake(lake_root, symbol="XAUUSD", n=600) -> pd.DataFrame:
    """Writes NATIVE M1 bars (M2 is resampled from M1 on read — see
    `sentinel_engine.service.bars.RESAMPLE_TF_MINUTES` — so a fixture that
    wrote directly at minutes=2 would be invisible to `tf=M2` reads)."""
    from sentinel_engine.lake.store import write_bars

    start = pd.Timestamp("2026-01-01T00:00:00", tz="UTC")
    idx = pd.date_range(start, periods=n, freq="1min", tz="UTC", name="time")
    closes = [4000.0 + 20.0 * math.sin(i / 9.0) + (i % 7) * 0.5 for i in range(n)]
    opens = [closes[i - 1] if i > 0 else closes[0] for i in range(n)]
    highs = [max(o, c) + 1.5 for o, c in zip(opens, closes)]
    lows = [min(o, c) - 1.5 for o, c in zip(opens, closes)]
    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [100] * n},
        index=idx,
    )
    write_bars(lake_root, symbol, 1, df)
    from sentinel_engine.service.bars import _resample_from_m1
    return _resample_from_m1(df, 2)


@pytest.fixture
def client_with_run(registry, tmp_path):
    lake_root = tmp_path / "lake"
    df = _mk_synthetic_lake(lake_root, "XAUUSD", 600)

    sid = registry.upsert_strategy("EMASAR", "emasar", "mt5")
    # sar3m3-style override: distinct from EMASAR_DEFAULTS so we can prove
    # the endpoint picks up the RUN's real params, not hardcoded defaults.
    vid = registry.upsert_variant(
        sid, "emasar_XAUUSD_M2_sar3m3_test",
        {"sar_step": 0.3, "sar_max": 0.3}, "M2", "XAUUSD", "original",
    )
    run_id = "sim-testindic0001"
    registry.insert_run({
        "run_id": run_id, "variant_id": vid, "params_hash": None,
        "engine": "sentinel-sim", "fidelity": "research",
        "periodo_desde": "2026-01-01", "periodo_hasta": "2026-01-02",
        "trades": 0, "net": 0.0,
    })

    shared_feed = FakeFeed()
    app = create_app(
        feed_factory=lambda name: shared_feed,
        instruments=("usdclp",),
        autostart_loop=False,
        registry=registry,
        lake_root=lake_root,
    )
    with TestClient(app) as c:
        yield c, registry, run_id, vid, df


def test_indicators_endpoint_returns_ema_and_sar_descriptors(client_with_run):
    client, _registry, run_id, _vid, _df = client_with_run
    resp = client.get(f"/api/runs/{run_id}/indicators", params={"tf": "M2"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tf"] == "M2"
    ids = [ind["id"] for ind in body["indicators"]]
    # SuperTrend added (design spec 2026-07-10, Component 7) alongside the
    # pre-existing EMA/SAR descriptors -- same list-of-descriptors shape.
    assert ids == ["ema_fast", "ema_slow", "sar", "supertrend"]


def test_indicators_reflect_run_params_not_hardcoded_defaults(client_with_run):
    """The sar3m3 variant overrides sar_step/sar_max to 0.3/0.3 — the
    response's SAR descriptor must echo THOSE values, proving param
    resolution used the run's real params, not EMASAR_DEFAULTS (0.02/0.20)."""
    client, _registry, run_id, _vid, _df = client_with_run
    resp = client.get(f"/api/runs/{run_id}/indicators", params={"tf": "M2"})
    body = resp.json()
    sar = next(i for i in body["indicators"] if i["id"] == "sar")
    assert sar["step"] == 0.3
    assert sar["max"] == 0.3
    assert sar["label"] == "SAR 0.3/0.3"
    ema_fast = next(i for i in body["indicators"] if i["id"] == "ema_fast")
    ema_slow = next(i for i in body["indicators"] if i["id"] == "ema_slow")
    assert ema_fast["period"] == _DEFAULT_PARAMS["ema_fast"]
    assert ema_slow["period"] == _DEFAULT_PARAMS["ema_slow"]
    assert ema_fast["label"] == f"EMA{_DEFAULT_PARAMS['ema_fast']}"


def test_indicators_parity_vs_direct_emasar_call(client_with_run):
    """The endpoint's points must equal a direct emasar.py call on the same
    bars/params — this IS the parity gate for this feature."""
    client, _registry, run_id, _vid, df = client_with_run
    resp = client.get(f"/api/runs/{run_id}/indicators", params={"tf": "M2"})
    body = resp.json()

    closes = df["close"].tolist()
    highs = df["high"].tolist()
    lows = df["low"].tolist()
    expected_fast = ema_series(closes, _DEFAULT_PARAMS["ema_fast"])
    expected_slow = ema_series(closes, _DEFAULT_PARAMS["ema_slow"])
    expected_sar, _trend = sar_series(highs, lows, 0.3, 0.3)

    ema_fast = next(i for i in body["indicators"] if i["id"] == "ema_fast")
    ema_slow = next(i for i in body["indicators"] if i["id"] == "ema_slow")
    sar = next(i for i in body["indicators"] if i["id"] == "sar")

    assert len(ema_fast["points"]) == len(expected_fast)
    for (_, val), exp in zip(ema_fast["points"], expected_fast):
        if exp is None:
            assert val is None
        else:
            assert val == pytest.approx(exp)
    for (_, val), exp in zip(ema_slow["points"], expected_slow):
        if exp is None:
            assert val is None
        else:
            assert val == pytest.approx(exp)
    for (_, val), exp in zip(sar["points"], expected_sar):
        if exp is None:
            assert val is None
        else:
            assert val == pytest.approx(exp)


def test_indicators_default_tf_is_run_native_tf(client_with_run):
    """No `?tf=` -> defaults to the run's native tf (variant.tf = M2 here),
    not a hardcoded M1."""
    client, _registry, run_id, _vid, _df = client_with_run
    resp = client.get(f"/api/runs/{run_id}/indicators")
    assert resp.status_code == 200
    assert resp.json()["tf"] == "M2"


def test_indicators_unknown_run_id_404(client_with_run):
    client, _registry, _run_id, _vid, _df = client_with_run
    resp = client.get("/api/runs/nonexistent/indicators")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "run_not_found"


def test_indicators_tf_with_no_bars_returns_empty_points_not_crash(client_with_run):
    client, _registry, run_id, _vid, _df = client_with_run
    resp = client.get(f"/api/runs/{run_id}/indicators", params={"tf": "M15"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tf"] == "M15"
    for ind in body["indicators"]:
        assert ind["points"] == []


def test_indicators_supertrend_descriptor_shape(client_with_run):
    """SuperTrend (design spec 2026-07-10-emasar-v1-mt5-integration, Component
    7): computed via the vendored emasar_ref, same list-of-descriptors shape
    as EMA/SAR so the frontend chips pick it up with no UI change."""
    client, _registry, run_id, _vid, _df = client_with_run
    resp = client.get(f"/api/runs/{run_id}/indicators", params={"tf": "M2"})
    body = resp.json()
    st = next(i for i in body["indicators"] if i["id"] == "supertrend")
    assert st["kind"] == "line"
    assert st["label"]
    assert isinstance(st["points"], list)
    assert len(st["points"]) == len(_df)


def test_indicators_supertrend_parity_vs_vendored_emasar_ref(client_with_run):
    """The endpoint's SuperTrend points must equal a direct call into the
    vendored `emasar_ref` (ATR-Wilder + SuperTrend recursion) on the same
    bars/params -- this IS the parity gate for this indicator."""
    client, _registry, run_id, _vid, df = client_with_run
    resp = client.get(f"/api/runs/{run_id}/indicators", params={"tf": "M2"})
    body = resp.json()
    st = next(i for i in body["indicators"] if i["id"] == "supertrend")

    from sentinel_engine.strategies.emasar_ref import _atr_wilder
    from sentinel_engine.strategies._supertrend_ref import supertrend as _supertrend_batch

    closes = df["close"].tolist()
    highs = df["high"].tolist()
    lows = df["low"].tolist()
    atr = _atr_wilder(highs, lows, closes, 10)
    _trend, expected_line = _supertrend_batch(
        highs, lows, closes, [a if a is not None else 0.0 for a in atr], 3.0,
    )
    expected_points = [None if atr[i] is None else expected_line[i] for i in range(len(atr))]

    assert len(st["points"]) == len(expected_points)
    for (_, val), exp in zip(st["points"], expected_points):
        if exp is None:
            assert val is None
        else:
            assert val == pytest.approx(exp)


def test_indicators_supertrend_empty_when_no_bars(client_with_run):
    client, _registry, run_id, _vid, _df = client_with_run
    resp = client.get(f"/api/runs/{run_id}/indicators", params={"tf": "M15"})
    body = resp.json()
    st = next(i for i in body["indicators"] if i["id"] == "supertrend")
    assert st["points"] == []


# ---------------------------------------------------------------------
# Defect B (Wave-2 plan 2026-07-10): the "candle-killer" bug. Without
# from/to, /indicators returns the ENTIRE lake history (100k+ points in
# production) regardless of the loaded candle window -- since all
# lightweight-charts series share one time scale, that pushes the actual
# candles off the visible logical range ("no candles visible, only SAR
# dots"). The invariant to enforce: overlay time-range subset-of candle
# time-range, never wider. With from/to given, only points inside
# [from, to] come back, though the underlying EMA/SAR/SuperTrend are
# computed on a frame that includes a WARMUP lookback before `from` so
# the in-window values themselves are seeded correctly (not re-started
# cold at `from`).
# ---------------------------------------------------------------------

def test_indicators_with_from_to_returns_strict_subset_of_full_range(client_with_run):
    client, _registry, run_id, _vid, _df = client_with_run
    full = client.get(f"/api/runs/{run_id}/indicators", params={"tf": "M2"}).json()
    full_points = full["indicators"][0]["points"]
    assert len(full_points) == 300  # 600 M1 bars -> 300 M2 bars

    # window to the middle third of the range.
    from_ts = full_points[100][0]
    to_ts = full_points[199][0]
    from_iso = pd.Timestamp(from_ts, unit="s", tz="UTC").isoformat()
    to_iso = pd.Timestamp(to_ts, unit="s", tz="UTC").isoformat()
    windowed = client.get(
        f"/api/runs/{run_id}/indicators",
        params={"tf": "M2", "from": from_iso, "to": to_iso},
    ).json()

    for ind in windowed["indicators"]:
        pts = ind["points"]
        assert len(pts) < len(full_points)  # strict subset in size
        assert len(pts) == 100  # exactly the [100,199] slice, inclusive
        for t, _v in pts:
            assert from_ts <= t <= to_ts


def test_indicators_with_from_to_is_warmup_seeded_not_cold_started(client_with_run):
    """The windowed EMA values must match a full-history EMA computed from
    bar 0 (properly seeded), NOT an EMA restarted cold at `from` -- proving
    the backend slices `[from - lookback : to]` for computation and only
    TRIMS the returned points to [from, to], rather than computing on a
    frame that starts at `from`."""
    client, _registry, run_id, _vid, df = client_with_run
    full = client.get(f"/api/runs/{run_id}/indicators", params={"tf": "M2"}).json()
    ema_fast_full = next(i for i in full["indicators"] if i["id"] == "ema_fast")["points"]

    from_ts = ema_fast_full[100][0]
    to_ts = ema_fast_full[199][0]
    from_iso = pd.Timestamp(from_ts, unit="s", tz="UTC").isoformat()
    to_iso = pd.Timestamp(to_ts, unit="s", tz="UTC").isoformat()
    windowed = client.get(
        f"/api/runs/{run_id}/indicators",
        params={"tf": "M2", "from": from_iso, "to": to_iso},
    ).json()
    ema_fast_win = next(i for i in windowed["indicators"] if i["id"] == "ema_fast")["points"]

    assert len(ema_fast_win) == 100
    for (t_full, v_full), (t_win, v_win) in zip(ema_fast_full[100:200], ema_fast_win):
        assert t_win == t_full
        assert v_win == pytest.approx(v_full)


def test_indicators_without_from_to_keeps_full_range_backward_compat(client_with_run):
    """No from/to -> the endpoint's pre-existing full-frame behavior is
    unchanged (callers that don't pass a window still get everything)."""
    client, _registry, run_id, _vid, _df = client_with_run
    resp = client.get(f"/api/runs/{run_id}/indicators", params={"tf": "M2"})
    assert resp.status_code == 200
    assert len(resp.json()["indicators"][0]["points"]) == 300


def test_indicators_bad_from_to_returns_400(client_with_run):
    client, _registry, run_id, _vid, _df = client_with_run
    resp = client.get(
        f"/api/runs/{run_id}/indicators",
        params={"tf": "M2", "from": "not-a-date"},
    )
    assert resp.status_code == 400
