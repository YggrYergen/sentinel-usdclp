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


# --------------------------------------------------------------------------
# SENTINEL_MACHINE_PROFILE per-process override (equipo 3, 2026-09-24).
# equipo 3 runs two MT5 stacks from ONE clone: stack #1 (AVA 101744074, armed)
# and stack #2 (second AVA demo, monitoring only). The env var lets a single
# subprocess select a different profile file. It must stay INERT when unset.
# --------------------------------------------------------------------------
def test_env_override_unset_uses_fixed_path(monkeypatch):
    """Unset env => the historical fixed path, byte-identical behavior."""
    monkeypatch.delenv(mp.PROFILE_PATH_ENV, raising=False)
    resolved, from_env = mp._resolve_default_path()
    assert resolved == mp.MACHINE_LOCAL_JSON
    assert from_env is False


def test_env_override_empty_is_treated_as_unset(monkeypatch):
    """An empty/whitespace value must not be mistaken for a real path."""
    monkeypatch.setenv(mp.PROFILE_PATH_ENV, "   ")
    resolved, from_env = mp._resolve_default_path()
    assert resolved == mp.MACHINE_LOCAL_JSON
    assert from_env is False


def test_env_override_selects_other_profile(tmp_path, monkeypatch):
    p = tmp_path / "machine_local.ava2.json"
    p.write_text(json.dumps({
        "terminal_path": r"C:\MT5_AVA2\terminal64.exe",
        "portable": False,
        "demo_login": 101744074,
    }), encoding="utf-8")
    monkeypatch.setenv(mp.PROFILE_PATH_ENV, str(p))
    profile = mp.load_profile()
    assert profile.terminal_path == mp.Path(r"C:\MT5_AVA2\terminal64.exe")
    assert profile.demo_login == 101744074
    assert profile.terminal_marker == "mt5_ava2"


def test_env_override_relative_resolves_against_repo_root(monkeypatch):
    monkeypatch.setenv(mp.PROFILE_PATH_ENV, r"scripts\live\whatever.json")
    resolved, from_env = mp._resolve_default_path()
    assert from_env is True
    assert resolved == mp.REPO_ROOT / "scripts" / "live" / "whatever.json"


def test_env_override_missing_file_is_hard_error(tmp_path, monkeypatch):
    """The dangerous case: a typo in the env var must NOT silently fall back
    to Machine 1 defaults / the other stack's profile -- it must raise."""
    missing = tmp_path / "does_not_exist.json"
    monkeypatch.setenv(mp.PROFILE_PATH_ENV, str(missing))
    with pytest.raises(mp.MachineProfileError) as exc:
        mp.load_profile()
    assert mp.PROFILE_PATH_ENV in str(exc.value)


def test_env_override_cannot_introduce_unsanctioned_login(tmp_path, monkeypatch):
    """The safety invariant: the env var only picks WHICH file is read; the
    login inside it still faces the hard-coded sanctioned set."""
    p = tmp_path / "machine_local.rogue.json"
    p.write_text(json.dumps({
        "terminal_path": r"C:\evil\terminal64.exe",
        "portable": False,
        "demo_login": 2883011573,  # the REAL account
    }), encoding="utf-8")
    monkeypatch.setenv(mp.PROFILE_PATH_ENV, str(p))
    with pytest.raises(mp.MachineProfileError):
        mp.load_profile()


def test_explicit_path_argument_still_wins_over_env(tmp_path, monkeypatch):
    """Existing call sites that pass path= explicitly must be unaffected."""
    explicit = tmp_path / "explicit.json"
    explicit.write_text(json.dumps({
        "terminal_path": r"C:\Explicit\terminal64.exe",
        "portable": False,
        "demo_login": 2883016567,
    }), encoding="utf-8")
    monkeypatch.setenv(mp.PROFILE_PATH_ENV, str(tmp_path / "ignored.json"))
    profile = mp.load_profile(path=explicit)
    assert profile.demo_login == 2883016567
