"""tests/analysis/test_pull_account_deals.py -- guard-focused tests for the
READ-ONLY cross-terminal deal-history puller
(scripts/analysis/pull_account_deals.py).

Covers the 2026-08-11 permission-separation change: this script no longer
gates reads on `guard_cuenta.SANCTIONED_DEMO_LOGINS` (that list answers "may
this process PLACE ORDERS here?", an order-authority question -- see the
PERMISSION SEPARATION note at the top of pull_account_deals.py).
`guard_cuenta.REAL_LOGIN` stays hard-blocked, unchanged. In its place this
module enforces its own read-scoped identity guard: connected login AND
connected server (both mandatory, independently checked) must match the
caller-supplied expectations, and `trade_mode` must be DEMO -- a real gate,
not just a print.

No test in this file imports MetaTrader5 or connects to a real terminal.
MT5 is always a hand-rolled duck-typed double (`_FakeMT5`).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts.analysis import pull_account_deals as pad
from sentinel_engine.live import guard_cuenta

ACCOUNT_902 = 2883016902
SERVER = "Capitaria-All"


class _FakeMT5:
    """Duck-typed MetaTrader5 module double. No network/terminal I/O."""

    def __init__(self, *, connected_login, connected_server, trade_mode=0,
                 total_deals=0, deals=None, init_ok=True):
        self.connected_login = connected_login
        self.connected_server = connected_server
        self.trade_mode = trade_mode
        self.total_deals = total_deals
        self.deals = deals if deals is not None else []
        self.init_ok = init_ok
        self.history_deals_get_calls = 0
        self.shutdown_calls = 0

    def initialize(self, path, login, password, server):
        return self.init_ok

    def account_info(self):
        return SimpleNamespace(
            login=self.connected_login,
            server=self.connected_server,
            trade_mode=self.trade_mode,
            balance=0.0, equity=0.0, currency="USD",
        )

    def history_deals_total(self, dfrom, dto):
        return self.total_deals

    def history_deals_get(self, dfrom, dto):
        self.history_deals_get_calls += 1
        return self.deals

    def shutdown(self):
        self.shutdown_calls += 1

    def last_error(self):
        return (0, "no error")


def _noop_sleep(_seconds):
    return None


# --- resolve_tester_exe / validate_tester_exe ------------------------------

def test_validate_tester_exe_missing_path_aborts(tmp_path):
    missing = tmp_path / "does_not_exist" / "terminal64.exe"
    err = pad.validate_tester_exe(missing)
    assert err is not None
    assert str(missing) in err


def test_validate_tester_exe_existing_file_ok(tmp_path):
    exe = tmp_path / "terminal64.exe"
    exe.write_bytes(b"stub")
    assert pad.validate_tester_exe(exe) is None


def test_resolve_tester_exe_precedence_cli_over_env_over_default(tmp_path):
    default = tmp_path / "default" / "terminal64.exe"
    cli_path = tmp_path / "cli" / "terminal64.exe"
    env_path = tmp_path / "env" / "terminal64.exe"
    assert pad.resolve_tester_exe(None, None, default) == default
    assert pad.resolve_tester_exe(None, str(env_path), default) == env_path
    assert pad.resolve_tester_exe(str(cli_path), str(env_path), default) == cli_path


# --- check_post_connect_guard (pure identity guard) -------------------------

def test_guard_rejects_real_login():
    err = pad.check_post_connect_guard(
        guard_cuenta.REAL_LOGIN, SERVER, 0,
        expected_login=guard_cuenta.REAL_LOGIN, expected_server=SERVER)
    assert err is not None
    assert str(guard_cuenta.REAL_LOGIN) in err


def test_guard_rejects_login_mismatch():
    err = pad.check_post_connect_guard(
        999999999, SERVER, 0,
        expected_login=ACCOUNT_902, expected_server=SERVER)
    assert err is not None


def test_guard_rejects_server_mismatch():
    err = pad.check_post_connect_guard(
        ACCOUNT_902, "SomeOtherServer", 0,
        expected_login=ACCOUNT_902, expected_server=SERVER)
    assert err is not None


def test_guard_rejects_non_demo_trade_mode():
    err = pad.check_post_connect_guard(
        ACCOUNT_902, SERVER, guard_cuenta.TRADE_MODE_REAL,
        expected_login=ACCOUNT_902, expected_server=SERVER)
    assert err is not None


def test_guard_accepts_matching_demo_identity():
    err = pad.check_post_connect_guard(
        ACCOUNT_902, SERVER, guard_cuenta.TRADE_MODE_DEMO,
        expected_login=ACCOUNT_902, expected_server=SERVER)
    assert err is None


def test_guard_does_not_require_sanctioned_demo_membership():
    """902 is deliberately NOT in guard_cuenta.SANCTIONED_DEMO_LOGINS (that
    list is order-authority, not read-authority). The read guard must still
    accept it -- this is the whole point of the permission separation."""
    assert ACCOUNT_902 not in guard_cuenta.SANCTIONED_DEMO_LOGINS
    err = pad.check_post_connect_guard(
        ACCOUNT_902, SERVER, guard_cuenta.TRADE_MODE_DEMO,
        expected_login=ACCOUNT_902, expected_server=SERVER)
    assert err is None


# --- pull_account_history: integration with a fake mt5 module --------------

def test_login_mismatch_aborts_and_reads_no_deal(tmp_path):
    fake = _FakeMT5(connected_login=1234567, connected_server=SERVER,
                     deals=[SimpleNamespace(ticket=1)])
    rc = pad.pull_account_history(
        fake, tester_exe=tmp_path / "terminal64.exe", login=ACCOUNT_902,
        server=SERVER, password="x", dfrom=pad._dt("2026-07-01"),
        dto=pad._dt("2026-08-01"), out_dir=tmp_path, sleep_fn=_noop_sleep)
    assert rc != 0
    assert fake.history_deals_get_calls == 0
    assert fake.shutdown_calls == 1


def test_server_mismatch_aborts_and_reads_no_deal(tmp_path):
    fake = _FakeMT5(connected_login=ACCOUNT_902, connected_server="WrongServer",
                     deals=[SimpleNamespace(ticket=1)])
    rc = pad.pull_account_history(
        fake, tester_exe=tmp_path / "terminal64.exe", login=ACCOUNT_902,
        server=SERVER, password="x", dfrom=pad._dt("2026-07-01"),
        dto=pad._dt("2026-08-01"), out_dir=tmp_path, sleep_fn=_noop_sleep)
    assert rc != 0
    assert fake.history_deals_get_calls == 0
    assert fake.shutdown_calls == 1


def test_non_demo_trade_mode_aborts_and_reads_no_deal(tmp_path):
    fake = _FakeMT5(connected_login=ACCOUNT_902, connected_server=SERVER,
                     trade_mode=guard_cuenta.TRADE_MODE_REAL,
                     deals=[SimpleNamespace(ticket=1)])
    rc = pad.pull_account_history(
        fake, tester_exe=tmp_path / "terminal64.exe", login=ACCOUNT_902,
        server=SERVER, password="x", dfrom=pad._dt("2026-07-01"),
        dto=pad._dt("2026-08-01"), out_dir=tmp_path, sleep_fn=_noop_sleep)
    assert rc != 0
    assert fake.history_deals_get_calls == 0
    assert fake.shutdown_calls == 1


def test_matching_identity_proceeds_and_reads_deals(tmp_path):
    fake = _FakeMT5(connected_login=ACCOUNT_902, connected_server=SERVER,
                     trade_mode=guard_cuenta.TRADE_MODE_DEMO, total_deals=0,
                     deals=[])
    rc = pad.pull_account_history(
        fake, tester_exe=tmp_path / "terminal64.exe", login=ACCOUNT_902,
        server=SERVER, password="x", dfrom=pad._dt("2026-07-01"),
        dto=pad._dt("2026-08-01"), out_dir=tmp_path, sleep_fn=_noop_sleep)
    assert rc == 0
    assert fake.history_deals_get_calls == 1
    assert fake.shutdown_calls == 1
    assert (tmp_path / f"{ACCOUNT_902}_deals_raw.csv").exists()


# --- main(): env-var credential handling + pre-connect checks --------------

def test_main_missing_password_env_var_aborts_without_revealing_values(monkeypatch, capsys):
    monkeypatch.delenv("MT5_PULL_PASSWORD", raising=False)
    rc = pad.main(["--login", str(ACCOUNT_902), "--server", SERVER])
    assert rc == 3
    captured = capsys.readouterr()
    assert "MT5_PULL_PASSWORD" in captured.err


def test_main_real_login_rejected_precheck(monkeypatch):
    monkeypatch.setenv("MT5_PULL_PASSWORD", "irrelevant-for-this-test")
    rc = pad.main(["--login", str(guard_cuenta.REAL_LOGIN), "--server", SERVER])
    assert rc == 2


def test_main_invalid_tester_exe_aborts(monkeypatch, tmp_path):
    monkeypatch.setenv("MT5_PULL_PASSWORD", "irrelevant-for-this-test")
    missing = tmp_path / "nope" / "terminal64.exe"
    rc = pad.main(["--login", str(ACCOUNT_902), "--server", SERVER,
                    "--tester-exe", str(missing)])
    assert rc == 4


# --- structural proof: no order-capable MT5 call anywhere in the module ----

def test_no_order_capable_calls_in_source():
    src = Path(pad.__file__).read_text(encoding="utf-8")
    for name in ("order_send(", "order_check(", "order_calc_margin(",
                 "order_calc_profit(", "positions_modify("):
        assert name not in src, f"found order-capable call pattern: {name}"
