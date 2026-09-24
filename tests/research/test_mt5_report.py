"""tests/research/test_mt5_report.py — TDD for `sentinel_engine.research.mt5_report`
(EMASAR V1 MT5-fidelity integration, design spec
docs/superpowers/specs/2026-07-10-emasar-v1-mt5-integration-design.md, Component 1).

Parses the UTF-16 MT5 Strategy-Tester `.htm` "Transacciones" (Deals) table +
the settings block. Two fixtures:
- `fixtures/mt5_report_emasar_sample.htm` — a small (9-row) UTF-16 copy
  preserving the real settings block + the 01-11 3-ficha anchor, for fast
  unit tests.
- The REAL file `D:/WebDev/TOKATA/mt5/reports/TOKATA_EMS_XAU_V1_M5_c2_sar3m3_m1.htm`
  (READ-ONLY, never touched/modified) — integration test asserting full deal
  count + totals match the report's own summary.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sentinel_engine.research.mt5_report import parse_mt5_report

FIXTURES = Path(__file__).parent / "fixtures"
REAL_REPORT = Path("D:/WebDev/TOKATA/mt5/reports/TOKATA_EMS_XAU_V1_M5_c2_sar3m3_m1.htm")


def test_parses_settings_block_from_sample():
    report = parse_mt5_report(FIXTURES / "mt5_report_emasar_sample.htm")
    settings = report["settings"]
    assert settings["expert"] == "TOKATA_EMASAR_v1"
    assert settings["symbol"] == "XAUUSD"
    assert settings["period"] == "M5"
    assert settings["model"] is None or isinstance(settings["model"], (str, int))
    assert settings["deposit_initial"] == pytest.approx(10000.0)
    assert settings["params"]["StrategyMode"] == "1"
    assert settings["params"]["ConfirmMode"] == "2"
    assert settings["params"]["SAR_Step"] == "0.3"
    assert settings["params"]["SAR_Max"] == "0.3"


def test_first_deal_row_is_initial_balance_deposit():
    report = parse_mt5_report(FIXTURES / "mt5_report_emasar_sample.htm")
    deals = report["deals"]
    first = deals[0]
    assert first["type"] == "balance"
    assert first["dir"] is None
    assert first["profit"] == pytest.approx(10000.0)
    assert first["balance"] == pytest.approx(10000.0)


def test_anchor_signal_three_fichas_in_at_same_ts_price():
    """2026.01.11 20:00:00: THREE 'buy in' deals @ 4511.96 (F1/F2/F3)."""
    report = parse_mt5_report(FIXTURES / "mt5_report_emasar_sample.htm")
    deals = report["deals"]
    ins = [d for d in deals if d["dir"] == "in" and d["ts"] == "2026.01.11 20:00:00"]
    assert len(ins) == 3
    for d in ins:
        assert d["type"] == "buy"
        assert d["price"] == pytest.approx(4511.96)
        assert d["symbol"] == "XAUUSD"
        assert d["volume"] == pytest.approx(0.1)


def test_anchor_signal_three_fichas_out_with_expected_profits():
    report = parse_mt5_report(FIXTURES / "mt5_report_emasar_sample.htm")
    deals = report["deals"]
    outs = [d for d in deals if d["dir"] == "out"]
    profits = sorted(d["profit"] for d in outs)
    assert profits == pytest.approx([154.10, 280.30, 551.70])
    for d in outs:
        assert d["type"] == "sell"


def test_deal_out_comment_sl_captured():
    report = parse_mt5_report(FIXTURES / "mt5_report_emasar_sample.htm")
    deals = report["deals"]
    sl_deal = next(d for d in deals if d["profit"] == pytest.approx(154.10))
    assert sl_deal["comment"] == "sl 4527.37"


def test_deals_ordered_by_order_number():
    report = parse_mt5_report(FIXTURES / "mt5_report_emasar_sample.htm")
    orders = [d["order"] for d in report["deals"]]
    assert orders == sorted(orders)


def test_malformed_htm_raises_named_error(tmp_path):
    bad = tmp_path / "bad.htm"
    bad.write_text("not an mt5 report", encoding="utf-8")
    with pytest.raises(ValueError, match=r"bad\.htm"):
        parse_mt5_report(bad)


@pytest.mark.skipif(not REAL_REPORT.exists(), reason="TOKATA repo not available")
class TestRealReport:
    def test_deal_count_and_settings(self):
        report = parse_mt5_report(REAL_REPORT)
        assert report["settings"]["symbol"] == "XAUUSD"
        assert report["settings"]["period"] == "M5"
        assert report["settings"]["params"]["StrategyMode"] == "1"
        assert report["settings"]["params"]["SAR_Step"] == "0.3"
        assert report["settings"]["params"]["SAR_Max"] == "0.3"
        # 139 deals total per the report's own "Transacciones" table.
        assert len(report["deals"]) == 139

    def test_anchor_signal_present(self):
        report = parse_mt5_report(REAL_REPORT)
        ins = [d for d in report["deals"]
               if d["dir"] == "in" and d["ts"] == "2026.01.11 20:00:00"]
        assert len(ins) == 3
        assert all(d["price"] == pytest.approx(4511.96) for d in ins)
        outs_profits = sorted(
            d["profit"] for d in report["deals"]
            if d["dir"] == "out" and d["ts"] in
            ("2026.01.11 20:10:40", "2026.01.11 21:00:00", "2026.01.12 01:05:00")
        )
        assert outs_profits == pytest.approx([154.10, 280.30, 551.70])

    def test_net_matches_summary(self):
        """Sum of all deal profit+commission+swap == report's own 'Beneficio
        Neto' (1624.60, matches the EMS-ORIG-sar3m3 ledger row per the design
        spec). The report's own deals-table footer totals (profit=1650.60,
        swap=-26.00, commission=0.00) reconcile to 1624.60 -- net is NOT the
        bare profit sum, it must include commission+swap per deal."""
        report = parse_mt5_report(REAL_REPORT)
        deal_rows = [d for d in report["deals"] if d["type"] != "balance"]
        net = sum(d["profit"] + d["commission"] + d["swap"] for d in deal_rows)
        assert net == pytest.approx(1624.60, abs=0.01)
