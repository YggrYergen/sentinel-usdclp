"""sentinel_engine.research.mt5_report — MT5 Strategy-Tester `.htm` parser
(EMASAR V1 MT5-fidelity integration, design spec
docs/superpowers/specs/2026-07-10-emasar-v1-mt5-integration-design.md,
Component 1).

Parses the UTF-16 `.htm` report emitted by the MT5 Strategy Tester: the
settings block (Experto/Símbolo/Período/Modelo/Parámetros de entrada,
Depósito inicial — for provenance) and the "Transacciones" (Deals) table
(one row PER DEAL: an "in" deal opens a position, an "out" deal closes it;
the FIRST data row is always the initial `balance` deposit).

Pure parsing — no MT5 package dependency, no network, no writes. Windows
10/11 safe: `pathlib.Path` + explicit `encoding="utf-16"` (the MT5 tester
always emits these reports as UTF-16 with a BOM).

Ground-truth anchor (verified against the real report, read-only):
`D:/WebDev/TOKATA/mt5/reports/TOKATA_EMS_XAU_V1_M5_c2_sar3m3_m1.htm` has,
at `2026.01.11 20:00:00`, THREE `buy in` deals @ `4511.96` (F1/F2/F3), later
closing as three `sell out` deals with profits +154.10/+280.30/+551.70.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Settings-block labels (Spanish, exact per the report) we care about for
# provenance. Order doesn't matter; regex search is per-label.
_SETTINGS_LABELS = {
    "Experto:": "expert",
    "Símbolo:": "symbol",
    "Período:": "period_raw",
    "Modelo:": "model",
}
_DEALS_TABLE_TITLE = "Transacciones"
_DEALS_HEADER_LABEL = "Fecha/Hora"


class Mt5ReportError(ValueError):
    """Raised when a `.htm` file does not look like an MT5 Strategy-Tester
    report (missing the Deals/"Transacciones" table) — named with the
    offending path so callers can report it without re-deriving context."""


def _num(text: str) -> float:
    """'1 051.50' / '1,051.50' -> 1051.5 · '' -> 0.0 (empty numeric cell)."""
    cleaned = re.sub(r"[^\d.\-]", "", text.replace(",", "."))
    if cleaned in ("", "-", "."):
        return 0.0
    return float(cleaned)


def _parse_settings(html: str) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "expert": None, "symbol": None, "period": None, "model": None,
        "deposit_initial": None, "params": {},
    }

    for label, key in _SETTINGS_LABELS.items():
        m = re.search(
            re.escape(label) + r"</td>\s*<td[^>]*><b>([^<]*)</b>", html,
        )
        if m:
            settings[key] = m.group(1).strip()

    # Período: "M5 (2026.01.02 - 2026.05.15)" -> tf token before the ' ('.
    period_raw = settings.pop("period_raw", None)
    if period_raw:
        settings["period"] = period_raw.split(" ")[0].strip()

    m = re.search(
        r"Depósito inicial:</td>\s*<td[^>]*><b>([^<]*)</b>", html,
    )
    if m:
        settings["deposit_initial"] = _num(m.group(1))

    # "Parámetros de entrada:" starts a run of rows of bare "<b>Key=Value</b>"
    # cells (no left-column label after the first row) until the next
    # labeled row (e.g. "Empresa:"). Capture every Key=Value pair in that
    # span, in order.
    m = re.search(r"Parámetros de entrada:</td>\s*<td[^>]*><b>(.*?)</table>", html, re.S)
    # The outer regex's `<b>` prefix is consumed by the match, so re-attach it
    # so the first Key=Value pair (StrategyMode=1) is captured too.
    span = "<b>" + m.group(1) if m else ""
    # Stop the span at the first row that carries a left-column label
    # (e.g. "Empresa:", "Divisa:") rather than a blank one — those rows
    # follow the param block and are not KEY=VALUE pairs.
    stop = re.search(r'colspan="3"\s*>[^<]*:</td>', span)
    if stop:
        span = span[: stop.start()]
    for pm in re.finditer(r"<b>([A-Za-z_][A-Za-z0-9_]*)=([^<]*)</b>", span):
        settings["params"][pm.group(1)] = pm.group(2).strip()

    return settings


_ROW_RE = re.compile(
    r'<tr bgcolor="[^"]*" align=right><td>([^<]*)</td>'  # ts
    r"<td>([^<]*)</td>"   # order/transaccion
    r"<td>([^<]*)</td>"   # symbol
    r"<td>([^<]*)</td>"   # type
    r"<td>([^<]*)</td>"   # dir
    r"<td>([^<]*)</td>"   # volume
    r"<td>([^<]*)</td>"   # price
    r"<td>([^<]*)</td>"   # order (repeated column, per MT5 layout)
    r"<td>([^<]*)</td>"   # commission
    r"<td>([^<]*)</td>"   # swap
    r"<td>([^<]*)</td>"   # profit
    r"<td>([^<]*)</td>"   # balance
    r"<td>([^<]*)</td></tr>"  # comment
)


def _parse_deals(html: str) -> list[dict[str, Any]]:
    title_idx = html.find(_DEALS_TABLE_TITLE)
    if title_idx == -1:
        raise Mt5ReportError(f"no '{_DEALS_TABLE_TITLE}' (Deals) table found")
    header_idx = html.find(_DEALS_HEADER_LABEL, title_idx)
    if header_idx == -1:
        raise Mt5ReportError(f"'{_DEALS_TABLE_TITLE}' table header not found")

    body = html[header_idx:]
    deals: list[dict[str, Any]] = []
    for m in _ROW_RE.finditer(body):
        ts, order_no, symbol, dtype, ddir, volume, price, order2, comm, swap, profit, balance, comment = m.groups()
        dtype = dtype.strip().lower()
        deals.append({
            "ts": ts.strip(),
            "order": int(order_no.strip()),
            "symbol": symbol.strip() or None,
            "type": dtype,
            "dir": (ddir.strip().lower() or None),
            "volume": _num(volume) if volume.strip() else None,
            "price": _num(price) if price.strip() else None,
            "mt5_order": int(order2.strip()) if order2.strip() else None,
            "commission": _num(comm),
            "swap": _num(swap),
            "profit": _num(profit),
            "balance": _num(balance),
            "comment": comment.strip() or None,
        })
    if not deals:
        raise Mt5ReportError(f"'{_DEALS_TABLE_TITLE}' table has no data rows")
    return deals


def parse_mt5_report(path: str | Path) -> dict[str, Any]:
    """Parse an MT5 Strategy-Tester `.htm` report -> `{"settings": {...},
    "deals": [...]}`. Raises `Mt5ReportError` (a `ValueError`) naming the
    file if it doesn't look like an MT5 report."""
    path = Path(path)
    try:
        html = path.read_text(encoding="utf-16")
    except (UnicodeError, UnicodeDecodeError) as exc:
        raise Mt5ReportError(f"{path}: not valid UTF-16 ({exc})") from exc

    if _DEALS_TABLE_TITLE not in html:
        raise Mt5ReportError(f"{path}: not an MT5 Strategy-Tester report (no Deals table)")

    settings = _parse_settings(html)
    deals = _parse_deals(html)
    return {"settings": settings, "deals": deals, "path": str(path)}
