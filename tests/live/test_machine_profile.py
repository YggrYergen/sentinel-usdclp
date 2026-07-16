"""tests/live/test_machine_profile.py -- per-machine profile loader
(sentinel_engine.live.machine_profile). Offline: no real MT5, no real
machine_local.json touched (all use tmp_path)."""
from __future__ import annotations

import json

import pytest

from sentinel_engine.live import machine_profile as mp


# --------------------------------------------------------------------------
# Defaults (Machine 1) when machine_local.json is absent.
# --------------------------------------------------------------------------
def test_defaults_when_no_json(tmp_path):
    missing = tmp_path / "machine_local.json"
    assert not missing.exists()
    profile = mp.load_profile(path=missing)
    assert profile.terminal_path == mp.Path(mp.DEFAULT_TERMINAL_PATH)
    assert profile.portable is True
    assert profile.demo_login == 2883015767
    assert profile.terminal_marker == "mt5_portable"


# --------------------------------------------------------------------------
# JSON override -- machine 2 style profile.
# --------------------------------------------------------------------------
def test_json_override_machine2(tmp_path):
    p = tmp_path / "machine_local.json"
    p.write_text(json.dumps({
        "terminal_path": r"C:\Program Files\Capitaria MT5 Terminal\terminal64.exe",
        "portable": False,
        "demo_login": 2883016567,
        "terminal_marker": "capitaria mt5 terminal",
    }), encoding="utf-8")
    profile = mp.load_profile(path=p)
    assert str(profile.terminal_path) == r"C:\Program Files\Capitaria MT5 Terminal\terminal64.exe"
    assert profile.portable is False
    assert profile.demo_login == 2883016567
    assert profile.terminal_marker == "capitaria mt5 terminal"


def test_json_override_derives_marker_when_absent(tmp_path):
    p = tmp_path / "machine_local.json"
    p.write_text(json.dumps({
        "terminal_path": r"C:\Program Files\Capitaria MT5 Terminal\terminal64.exe",
        "portable": False,
        "demo_login": 2883016567,
    }), encoding="utf-8")
    profile = mp.load_profile(path=p)
    assert profile.terminal_marker == "capitaria mt5 terminal"


# --------------------------------------------------------------------------
# Unsanctioned login MUST be rejected loudly at load time.
# --------------------------------------------------------------------------
def test_unsanctioned_login_rejected(tmp_path):
    p = tmp_path / "machine_local.json"
    p.write_text(json.dumps({
        "terminal_path": r"C:\evil\terminal64.exe",
        "portable": False,
        "demo_login": 9999999,
    }), encoding="utf-8")
    with pytest.raises(mp.MachineProfileError):
        mp.load_profile(path=p)


def test_missing_required_key_rejected(tmp_path):
    p = tmp_path / "machine_local.json"
    p.write_text(json.dumps({"portable": True, "demo_login": 2883015767}), encoding="utf-8")
    with pytest.raises(mp.MachineProfileError):
        mp.load_profile(path=p)


def test_malformed_json_rejected(tmp_path):
    p = tmp_path / "machine_local.json"
    p.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(mp.MachineProfileError):
        mp.load_profile(path=p)
