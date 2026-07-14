"""tests/scripts/test_check_dryrun_intent_parity.py -- DRY-RUN intent parity
checker tests. All offline/synthetic: no MT5, no real lake. Exercises the
pure log parser (`parse_audit_log`/`parse_action_list`) and the pure diff
core (`diff_cycle`/`run_check`) directly, and the CLI exit codes via a tmp
log file + a monkeypatched `load_bars`."""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone

import pytest

from scripts.live import check_dryrun_intent_parity as mod
from sentinel_engine.strategies.live_configs_20 import CONFIGS_20


def _cfg(cid: str) -> dict:
    return next(c for c in CONFIGS_20 if c["id"] == cid)


def _synthetic_bars(n=600, seed=7, tf_s=300, start=None):
    rnd = random.Random(seed)
    bars, price = [], 4500.0
    base = start if start is not None else int(datetime(2026, 7, 13, tzinfo=timezone.utc).timestamp())
    for k in range(n):
        drift = rnd.uniform(-1.5, 2.2)
        price += drift
        o, c = price - drift, price
        h = max(o, c) + abs(rnd.uniform(0.3, 1.2))
        lo = min(o, c) - abs(rnd.uniform(0.3, 1.2))
        bars.append({"open": o, "high": h, "low": lo, "close": c, "t": base + k * tf_s})
    return bars


# --------------------------------------------------------------------------
# 1) Log parser happy path.
# --------------------------------------------------------------------------

def test_parse_audit_log_happy_path():
    text = (
        "2026-07-13 22:25:11,039 INFO === cycle 2026-07-14T02:25:11.039742+00:00 "
        "| guard OK | kill=False | dry_run=True ===\n"
        "2026-07-13 22:25:11,372 INFO [SS-M2] bar=2026-07-13T22:22:00+00:00 actions: none\n"
        "2026-07-13 22:25:11,512 INFO [V06D-M2] bar=2026-07-13T22:22:00+00:00 "
        "actions: OPEN/F1, MODIFY/F2\n"
    )
    cycles, stats = mod.parse_audit_log(text)
    assert stats.parse_skipped == 0
    assert len(cycles) == 2
    c0, c1 = cycles
    assert c0.config_id == "SS-M2" and c0.intents == []
    assert c1.config_id == "V06D-M2"
    assert [(i.kind, i.ficha) for i in c1.intents] == [("OPEN", "F1"), ("MODIFY", "F2")]
    expected_t = int(datetime(2026, 7, 13, 22, 22, 0, tzinfo=timezone.utc).timestamp())
    assert c1.bar_t == expected_t


# --------------------------------------------------------------------------
# 2) Tolerant skip: garbage / malformed lines never crash, get counted.
# --------------------------------------------------------------------------

def test_parse_audit_log_tolerant_skip():
    text = (
        "not a log line at all\n"
        "2026-07-13 22:25:11,372 INFO some random message, no actions here\n"
        "2026-07-13 22:25:11,372 INFO [BROKEN] bar=not-a-timestamp actions: none\n"
        "2026-07-13 22:25:11,372 WARNING [SS-M2] no bars available (market closed / no data)\n"
        "2026-07-13 22:25:12,078 INFO [SS-M5] bar=2026-07-13T22:20:00+00:00 actions: none\n"
    )
    cycles, stats = mod.parse_audit_log(text)
    assert len(cycles) == 1
    assert cycles[0].config_id == "SS-M5"
    assert stats.parse_skipped == 1  # the [BROKEN] line has "actions:" but bad timestamp


# --------------------------------------------------------------------------
# 3) MISSED_SIGNAL: "actions: none" logged, but lake-recomputed state shows a
#    new entry on that bar.
# --------------------------------------------------------------------------

def test_missed_signal_detection():
    cfg = _cfg("V09-CTRL-M5")
    tf_s = mod.TF_SECONDS[cfg["tf"]]
    bars = _synthetic_bars(n=400, seed=3, tf_s=tf_s)

    # find a bar index where an ENTRY event actually fires under this config.
    events, _ = mod.simular_variant(bars, return_state=True, **cfg["kwargs"])
    entry_idx = next(ev["idx"] for ev in events if ev["motivo"].startswith("ENTRY"))
    assert entry_idx > 0

    bar_t = bars[entry_idx]["t"]
    cycle = mod.ParsedCycle(line_no=1, log_ts="x", config_id=cfg["id"], bar_t=bar_t, intents=[])
    findings = mod.diff_cycle(cycle, bars, cfg, tf_s)
    kinds = [f.kind for f in findings]
    assert "MISSED_SIGNAL" in kinds
    assert all(f.hard for f in findings if f.kind == "MISSED_SIGNAL")


# --------------------------------------------------------------------------
# 4) SIGNAL_MISMATCH: executor logs OPEN for a ficha the lake-recomputed
#    state does NOT have open on that bar.
# --------------------------------------------------------------------------

def test_signal_mismatch_detection():
    cfg = _cfg("V09-CTRL-M5")
    tf_s = mod.TF_SECONDS[cfg["tf"]]
    bars = _synthetic_bars(n=400, seed=3, tf_s=tf_s)

    events, _ = mod.simular_variant(bars, return_state=True, **cfg["kwargs"])
    entry_idxs = {ev["idx"] for ev in events if ev["motivo"].startswith("ENTRY")}
    # pick a bar with NO entry -> lake-recomputed desired open state should
    # not gain F1 fresh here in a way that supports an OPEN/F1 the executor
    # claims. Use a flat bar (no open positions at all) for a clean mismatch.
    flat_idx = None
    for idx in range(5, len(bars)):
        if idx in entry_idxs:
            continue
        _e2, snap = mod.simular_variant(bars[: idx + 1], return_state=True, **cfg["kwargs"])
        if not snap["open"]:
            flat_idx = idx
            break
    assert flat_idx is not None

    bar_t = bars[flat_idx]["t"]
    cycle = mod.ParsedCycle(line_no=2, log_ts="x", config_id=cfg["id"], bar_t=bar_t,
                            intents=[mod.ParsedIntent(kind="OPEN", ficha="F1")])
    findings = mod.diff_cycle(cycle, bars, cfg, tf_s)
    kinds = [f.kind for f in findings]
    assert "SIGNAL_MISMATCH" in kinds
    assert all(f.hard for f in findings if f.kind == "SIGNAL_MISMATCH")


# --------------------------------------------------------------------------
# 5) "actions: none" + flat lake state at that bar -> clean (no findings).
# --------------------------------------------------------------------------

def test_none_actions_flat_state_is_clean():
    cfg = _cfg("V09-CTRL-M5")
    tf_s = mod.TF_SECONDS[cfg["tf"]]
    bars = _synthetic_bars(n=400, seed=3, tf_s=tf_s)

    events, _ = mod.simular_variant(bars, return_state=True, **cfg["kwargs"])
    entry_idxs = {ev["idx"] for ev in events if ev["motivo"].startswith("ENTRY")}
    flat_idx = next(idx for idx in range(5, len(bars)) if idx not in entry_idxs)

    bar_t = bars[flat_idx]["t"]
    cycle = mod.ParsedCycle(line_no=3, log_ts="x", config_id=cfg["id"], bar_t=bar_t, intents=[])
    findings = mod.diff_cycle(cycle, bars, cfg, tf_s)
    assert findings == []


# --------------------------------------------------------------------------
# 5b) BAR_EDGE_LAG: executor's cycle bar_t is strictly newer than the last
#     available lake bar -> exactly one non-hard BAR_EDGE_LAG finding, no
#     recompute, no hard findings -- even though the executor logged OPEN
#     actions that would otherwise be checked against lake state.
# --------------------------------------------------------------------------

def test_bar_edge_lag_not_hard():
    cfg = _cfg("V09-CTRL-M5")
    tf_s = mod.TF_SECONDS[cfg["tf"]]
    bars = _synthetic_bars(n=400, seed=3, tf_s=tf_s)

    lake_tail_t = bars[-1]["t"]
    bar_t = lake_tail_t + tf_s  # strictly newer than lake tail

    cycle = mod.ParsedCycle(line_no=4, log_ts="x", config_id=cfg["id"], bar_t=bar_t,
                            intents=[mod.ParsedIntent(kind="OPEN", ficha="F1")])
    findings = mod.diff_cycle(cycle, bars, cfg, tf_s)
    kinds = [f.kind for f in findings]
    assert kinds == ["BAR_EDGE_LAG"]
    assert all(not f.hard for f in findings)
    assert all(f.kind not in mod.HARD_KINDS for f in findings)


# --------------------------------------------------------------------------
# 6) Exit codes via the CLI main(): 0 (clean), 1 (hard finding), 2 (usage).
# --------------------------------------------------------------------------

def test_cli_exit_code_usage_error(tmp_path):
    missing = tmp_path / "does_not_exist.log"
    rc = mod.main(["--log", str(missing)])
    assert rc == 2


def test_cli_exit_code_unknown_config(tmp_path):
    log_path = tmp_path / "audit.log"
    log_path.write_text(
        "2026-07-13 22:25:11,372 INFO [SS-M2] bar=2026-07-13T22:22:00+00:00 actions: none\n",
        encoding="utf-8")
    rc = mod.main(["--log", str(log_path), "--configs", "NOT-A-CONFIG"])
    assert rc == 2


def test_cli_exit_code_clean_run(tmp_path, monkeypatch):
    cfg = _cfg("V09-CTRL-M5")
    tf_s = mod.TF_SECONDS[cfg["tf"]]
    bars = _synthetic_bars(n=400, seed=3, tf_s=tf_s)
    events, _ = mod.simular_variant(bars, return_state=True, **cfg["kwargs"])
    entry_idxs = {ev["idx"] for ev in events if ev["motivo"].startswith("ENTRY")}
    flat_idx = next(idx for idx in range(5, len(bars)) if idx not in entry_idxs)
    bar_t = bars[flat_idx]["t"]

    iso = datetime.fromtimestamp(bar_t, tz=timezone.utc).isoformat()
    log_path = tmp_path / "audit.log"
    log_path.write_text(
        f"2026-07-13 22:25:11,372 INFO [{cfg['id']}] bar={iso} actions: none\n",
        encoding="utf-8")

    monkeypatch.setattr(mod, "load_bars", lambda *a, **kw: bars)
    rc = mod.main(["--log", str(log_path), "--configs", cfg["id"]])
    assert rc == 0


def test_cli_exit_code_hard_finding(tmp_path, monkeypatch):
    cfg = _cfg("V09-CTRL-M5")
    tf_s = mod.TF_SECONDS[cfg["tf"]]
    bars = _synthetic_bars(n=400, seed=3, tf_s=tf_s)
    events, _ = mod.simular_variant(bars, return_state=True, **cfg["kwargs"])
    entry_idx = next(ev["idx"] for ev in events if ev["motivo"].startswith("ENTRY"))
    bar_t = bars[entry_idx]["t"]

    iso = datetime.fromtimestamp(bar_t, tz=timezone.utc).isoformat()
    log_path = tmp_path / "audit.log"
    log_path.write_text(
        f"2026-07-13 22:25:11,372 INFO [{cfg['id']}] bar={iso} actions: none\n",
        encoding="utf-8")

    monkeypatch.setattr(mod, "load_bars", lambda *a, **kw: bars)
    json_out = tmp_path / "out.json"
    rc = mod.main(["--log", str(log_path), "--configs", cfg["id"], "--json", str(json_out)])
    assert rc == 1
    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["configs"][cfg["id"]]["hard"] >= 1
