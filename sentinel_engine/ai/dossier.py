"""sentinel_engine.ai.dossier — position dossier builder (CT-7, Task C3a).

`build_position_dossier(trade_id, tfs=["M5"]) -> Dossier` where
`Dossier = {"xml": str, "token_estimate": int, "sections": dict[str, int]}`.

Format is the LITERAL §3 template of
`docs/superpowers/specs/2026-07-12-llm-timeseries-context-research.md`:
markdown tables for OHLCV series, fixed decimal precision, compact JSON for
the (small, semi-irregular) trade-record and derived-stats sections, each
section wrapped in Anthropic's documented
`<document index="n"><source>...</source><document_content>...</document_content></document>`
pattern, all sections nested inside a top-level `<documents>` element. Stats
(MAE/MFE-as-%-of-SL/TP-distance, R-multiple) are server-computed here, never
left for the model to derive. The trader's `<question>` is explicitly NOT
included — the caller appends it last, after this dossier's XML, per the
"data before question" ordering the research doc quantifies (§RQ6, "up to
30%" quality improvement).

DETERMINISM: no `datetime.now()`, no wall-clock, no randomness — same
discipline `sentinel_engine/ai_context.py` already mandates, needed here
additionally for prompt-cache-hit-rate stability (research doc §RQ6/RQ8).

`token_estimate` uses a simple, documented heuristic: `ceil(len(xml_chars) /
3.5)` — NOT a real tokenizer call (no new deps). 3.5 chars/token is a common
rough English/markdown estimate; good enough for budget enforcement, not
claimed to be exact.

Budget: position dossier target <= 8,000 estimated tokens (research doc
§3). If the initial render exceeds the budget, the largest bar table is
trimmed by dropping its OLDEST rows (front of the table) first, re-rendered,
and re-measured, repeating until under budget or only the entry/exit anchor
rows remain. A trim is recorded via `sections["trim_applied"] = True`.

Data access (read-only): trade + variant + strategy rows come from the
`ResearchRegistry` sqlite DB (`sentinel_engine/research/registry2.py`
schema, read directly — no registry method returns a single trade by id
today, so this module reads the `trade`/`variant`/`strategy` tables
directly via a plain sqlite3 connection). Bars come from the lake via
`sentinel_engine.service.bars.load_tf_frame` (read-only, existing helper —
handles native + M2/M10-resampled timeframes uniformly).
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from sentinel_engine.research.registry2 import DEFAULT_DB_PATH
from sentinel_engine.service.bars import load_tf_frame
from sentinel_engine.strategies.emasar import ema_series, sar_series

# Heuristic chars-per-token divisor for `token_estimate` -- see module
# docstring. Not a real tokenizer; documented approximation only.
CHARS_PER_TOKEN = 3.5

# Position dossier target budget (research doc §3: "3,000-8,000 tokens").
BUDGET_TOKENS = 8000

# Strategy dossier target budget (Task C3b brief: <= 10K estimated tokens
# for the stuffed portion; research doc §4 gives 8-20K as the general range
# -- this app pins the ceiling at 10K).
BUDGET_TOKENS_STRATEGY = 10000

# Recent-runs table default size for the strategy dossier (newest first).
RECENT_RUNS_LIMIT = 50

# Bars-before-entry / bars-after-exit window per timeframe (research doc §3
# worked example uses N=20/M=20 at the entry timeframe as the default).
BARS_BEFORE_ENTRY = 20
BARS_AFTER_EXIT = 20

# Fixed decimal precision for price columns (research doc §RQ3: fixed,
# consistent decimal precision per column/instrument). XAUUSD-style 2dp is
# used uniformly here -- no per-instrument tick-size table exists in this
# module's minimal scope (documented simplification, see task report).
PRICE_DP = 2
VOLUME_DP = 2

DEFAULT_LAKE_ROOT = Path("data/lake")

# Indicator columns (§3 template: ema8/ema20/sar/rsi14). Math is REUSED from
# `sentinel_engine.strategies.emasar` (ema_series / sar_series) -- the same
# functions the `/api/bars` overlays endpoint uses
# (`sentinel_engine/service/routers/bars.py`), with the SAME params and the
# same warmup pattern: read `_INDICATOR_WARMUP_BARS` extra bars before the
# display window, compute over the extended series, clip back to the window.
# NOTE: `rsi14` is OMITTED -- no standalone RSI-series function exists in
# this codebase (technical.py consumes pre-computed rsi signal values);
# declared as a deviation in the task report.
_INDICATOR_WARMUP_BARS = 200
_EMA8_PERIOD = 8
_EMA20_PERIOD = 20
_SAR_STEP = 0.02
_SAR_MAX = 0.20


class DossierError(ValueError):
    """Raised for a bad `build_position_dossier` request (unknown trade_id, ...)."""


def _fetch_trade_row(db_path: Path, trade_id: str) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT t.*, v.instrumento AS instrumento, v.tf AS variant_tf
               FROM trade t
               LEFT JOIN run r ON t.run_id = r.run_id
               LEFT JOIN variant v ON r.variant_id = v.variant_id
               WHERE t.trade_id = ?""",
            (trade_id,),
        ).fetchone()
        if row is None:
            raise DossierError(f"unknown trade_id: {trade_id!r}")
        return dict(row)
    finally:
        conn.close()


def _fmt(v: float | None, dp: int) -> str:
    if v is None:
        return "n/a"
    return f"{v:.{dp}f}"


def _trade_record_section(trade: dict[str, Any]) -> str:
    lines = [
        "{",
        f'  "trade_id": "{trade["trade_id"]}",',
        f'  "instrument": "{trade.get("instrumento") or "n/a"}",',
        f'  "side": "{trade.get("side") or "n/a"}",',
        f'  "ts_in": "{trade.get("ts_in")}",',
        f'  "ts_out": "{trade.get("ts_out")}",',
        f'  "px_in": {_fmt(trade.get("px_in"), PRICE_DP)},',
        f'  "px_out": {_fmt(trade.get("px_out"), PRICE_DP)},',
        f'  "sl": {_fmt(trade.get("sl"), PRICE_DP)},',
        f'  "tp": {_fmt(trade.get("tp"), PRICE_DP)},',
        f'  "volume": {_fmt(trade.get("volume"), VOLUME_DP)},',
        f'  "exit_reason": "{trade.get("exit_reason") or "n/a"}",',
        f'  "exit_reason_source": "{trade.get("exit_reason_source") or "n/a"}",',
        f'  "pnl_usd": {_fmt(trade.get("pnl"), 2)},',
        f'  "mae_pips": {_fmt(trade.get("mae"), 1)},',
        f'  "mfe_pips": {_fmt(trade.get("mfe"), 1)},',
        f'  "hold_time_min": {trade.get("hold_time_min") if trade.get("hold_time_min") is not None else "null"}',
        "}",
    ]
    return "\n".join(lines)


def _derived_stats_section(trade: dict[str, Any]) -> str:
    """Server-computed relationships the model would otherwise have to
    derive in-context (research doc §3/§RQ5: aggregation-class computation
    the model is structurally weak at)."""
    px_in = trade.get("px_in")
    px_out = trade.get("px_out")
    sl = trade.get("sl")
    tp = trade.get("tp")
    side = trade.get("side")

    lines = []
    if px_in is not None and sl is not None:
        sl_dist = abs(px_in - sl)
        mae = trade.get("mae")
        mae_pct = (abs(mae) / sl_dist * 100.0) if (mae is not None and sl_dist) else None
        lines.append(
            f"MAE as % of SL distance: {_fmt(mae_pct, 1)}%"
            if mae_pct is not None else "MAE as % of SL distance: n/a"
        )
    if px_in is not None and tp is not None:
        tp_dist = abs(tp - px_in)
        mfe = trade.get("mfe")
        mfe_pct = (abs(mfe) / tp_dist * 100.0) if (mfe is not None and tp_dist) else None
        lines.append(
            f"MFE as % of TP distance: {_fmt(mfe_pct, 1)}%"
            if mfe_pct is not None else "MFE as % of TP distance: n/a"
        )
    if px_in is not None and px_out is not None and sl is not None:
        sl_dist = abs(px_in - sl)
        realized = (px_out - px_in) if side == "LONG" else (px_in - px_out)
        r_mult = (realized / sl_dist) if sl_dist else None
        lines.append(
            f"R-multiple realized: {_fmt(r_mult, 2)}R"
            if r_mult is not None else "R-multiple realized: n/a"
        )
    return "\n".join(lines) if lines else "n/a"


def _fmt_opt(v, dp: int) -> str:
    """Format an optional/NaN-able indicator value at fixed dp."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    return f"{float(v):.{dp}f}"


def _bars_table(df: pd.DataFrame, entry_idx: int, exit_idx: int | None) -> str:
    header = "| idx | time | open | high | low | close | volume | ema8 | ema20 | sar |"
    sep = "|----:|------|-----:|-----:|----:|------:|-------:|-----:|------:|----:|"
    rows = [header, sep]
    has_ind = "ema8" in df.columns
    for i, (ts, row) in enumerate(df.iterrows()):
        offset = i - entry_idx
        marker = ""
        if i == entry_idx:
            marker = " <<< ENTRY BAR"
        elif exit_idx is not None and i == exit_idx:
            marker = " <<< EXIT BAR"
        time_str = ts.strftime("%H:%M")
        ema8 = _fmt_opt(row.get("ema8") if has_ind else None, PRICE_DP)
        ema20 = _fmt_opt(row.get("ema20") if has_ind else None, PRICE_DP)
        sar = _fmt_opt(row.get("sar") if has_ind else None, PRICE_DP)
        rows.append(
            f"| {offset:+d} | {time_str} | {_fmt(row['open'], PRICE_DP)} | "
            f"{_fmt(row['high'], PRICE_DP)} | {_fmt(row['low'], PRICE_DP)} | "
            f"{_fmt(row['close'], PRICE_DP)} | {_fmt(row['volume'], VOLUME_DP)} | "
            f"{ema8} | {ema20} | {sar}{marker} |"
        )
    return "\n".join(rows)


def _load_bars_window(
    lake_root: Path, symbol: str, tf: str, ts_in: pd.Timestamp, ts_out: pd.Timestamp | None,
    bars_before: int, bars_after: int,
) -> tuple[pd.DataFrame, int, int | None]:
    df = load_tf_frame(lake_root, symbol, tf)
    if df.empty:
        return df, 0, None
    entry_pos = df.index.searchsorted(ts_in, side="left")
    entry_pos = min(entry_pos, len(df) - 1)
    start = max(0, entry_pos - bars_before)

    exit_pos = None
    if ts_out is not None:
        exit_pos = df.index.searchsorted(ts_out, side="left")
        exit_pos = min(exit_pos, len(df) - 1)
        end = min(len(df), exit_pos + bars_after + 1)
    else:
        end = min(len(df), entry_pos + bars_after + 1)

    # Indicator warmup: compute over `_INDICATOR_WARMUP_BARS` extra bars
    # BEFORE the window, then clip back -- same pattern (and same underlying
    # ema_series/sar_series functions) as the /api/bars overlays endpoint.
    warm_start = max(0, start - _INDICATOR_WARMUP_BARS)
    warm = df.iloc[warm_start:end].copy()
    closes = [float(c) for c in warm["close"]]
    highs = [float(h) for h in warm["high"]]
    lows = [float(l) for l in warm["low"]]
    warm["ema8"] = ema_series(closes, _EMA8_PERIOD)
    warm["ema20"] = ema_series(closes, _EMA20_PERIOD)
    sar_vals, _trend = sar_series(highs, lows, _SAR_STEP, _SAR_MAX)
    warm["sar"] = sar_vals

    window = warm.iloc[start - warm_start:]
    entry_idx = entry_pos - start
    exit_idx = (exit_pos - start) if exit_pos is not None else None
    return window, entry_idx, exit_idx


def _document(index: int, source: str, content: str) -> str:
    return (
        f'  <document index="{index}">\n'
        f"    <source>{source}</source>\n"
        f"    <document_content>\n"
        f"{content}\n"
        f"    </document_content>\n"
        f"  </document>"
    )


def _render(
    trade: dict[str, Any],
    tf_windows: dict[str, tuple[pd.DataFrame, int, int | None]],
) -> tuple[str, dict[str, int]]:
    sections: dict[str, int] = {}
    docs = []
    idx = 1

    trade_content = _trade_record_section(trade)
    sections["trade_record"] = len(trade_content)
    docs.append(_document(idx, f"trade_record:{trade['trade_id']}", trade_content))
    idx += 1

    stats_content = _derived_stats_section(trade)
    sections["derived_stats"] = len(stats_content)
    docs.append(_document(idx, f"derived_stats:{trade['trade_id']}", stats_content))
    idx += 1

    for tf, (df, entry_idx, exit_idx) in tf_windows.items():
        table = _bars_table(df, entry_idx, exit_idx)
        key = f"bars:{tf}"
        sections[key] = len(table)
        source = f"bars:{tf}:{trade['trade_id']}:bars_before_entry={BARS_BEFORE_ENTRY}:bars_after_exit={BARS_AFTER_EXIT}"
        docs.append(_document(idx, source, table))
        idx += 1

    xml = "<documents>\n\n" + "\n\n".join(docs) + "\n\n</documents>"
    return xml, sections


def _token_estimate(xml: str) -> int:
    return math.ceil(len(xml) / CHARS_PER_TOKEN)


def build_position_dossier(
    trade_id: str,
    tfs: list[str] | None = None,
    *,
    db_path: Path | None = None,
    lake_root: Path | None = None,
) -> dict[str, Any]:
    """Build the position dossier for `trade_id` per CT-7. Returns
    `{"xml": str, "token_estimate": int, "sections": dict[str, int]}`.

    `tfs` defaults to `["M5"]`. `db_path`/`lake_root` default to this repo's
    standard locations (`ResearchRegistry.DEFAULT_DB_PATH`,
    `data/lake`) but are injectable for tests.
    """
    if tfs is None:
        tfs = ["M5"]
    db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    lake_root = Path(lake_root) if lake_root is not None else DEFAULT_LAKE_ROOT

    trade = _fetch_trade_row(db_path, trade_id)
    symbol = trade.get("instrumento")
    ts_in = pd.Timestamp(trade["ts_in"])
    if ts_in.tzinfo is None:
        ts_in = ts_in.tz_localize("UTC")
    ts_out_raw = trade.get("ts_out")
    ts_out = None
    if ts_out_raw:
        ts_out = pd.Timestamp(ts_out_raw)
        if ts_out.tzinfo is None:
            ts_out = ts_out.tz_localize("UTC")

    # Server-computed hold time (§3 template `hold_time_min`); null if the
    # position has no ts_out (still open).
    trade["hold_time_min"] = (
        int(round((ts_out - ts_in).total_seconds() / 60.0)) if ts_out is not None else None
    )

    bars_before = BARS_BEFORE_ENTRY
    bars_after = BARS_AFTER_EXIT
    tf_windows: dict[str, tuple[pd.DataFrame, int, int | None]] = {}
    for tf in tfs:
        tf_windows[tf] = _load_bars_window(
            lake_root, symbol, tf, ts_in, ts_out, bars_before, bars_after,
        )

    xml, sections = _render(trade, tf_windows)
    token_estimate = _token_estimate(xml)

    trim_applied = False
    # Budget enforcement: trim bar tables' OLDEST rows first (front of the
    # table, furthest from entry), re-render, re-measure, repeat until
    # under budget (research doc §3 budget: <= 8,000 tokens for a position
    # dossier). Once the front is exhausted (only entry..last-row remains),
    # fall back to trimming the trailing rows furthest from exit -- the
    # entry and exit anchor rows themselves are always preserved. Each pass
    # drops a bulk estimate of rows (based on average chars/row) rather
    # than one row at a time, so this converges in O(few) passes even for
    # very oversized fixtures.
    while token_estimate > BUDGET_TOKENS:
        candidates = [tf for tf, (df, _, _) in tf_windows.items() if len(df) > 2]
        if not candidates:
            break
        target_tf = max(candidates, key=lambda tf: len(tf_windows[tf][0]))
        df, entry_idx, exit_idx = tf_windows[target_tf]

        excess_tokens = token_estimate - BUDGET_TOKENS
        excess_chars = excess_tokens * CHARS_PER_TOKEN
        avg_row_chars = max(1.0, sections.get(f"bars:{target_tf}", len(df) * 40) / max(1, len(df)))
        want_drop = max(1, int(excess_chars / avg_row_chars) + 1)

        if entry_idx > 0:
            # Front trim: drop oldest rows, capped so the entry row survives.
            drop_n = min(entry_idx, want_drop)
            df = df.iloc[drop_n:]
            entry_idx -= drop_n
            exit_idx = (exit_idx - drop_n) if exit_idx is not None else None
        else:
            # Front exhausted -- trim trailing rows, capped so the exit row
            # (or at least one row past entry) survives.
            last_keep = exit_idx if exit_idx is not None else entry_idx
            max_tail_drop = max(0, (len(df) - 1) - last_keep)
            drop_n = min(max_tail_drop, want_drop)
            if drop_n <= 0:
                break
            df = df.iloc[: len(df) - drop_n]

        tf_windows[target_tf] = (df, entry_idx, exit_idx)
        trim_applied = True
        xml, sections = _render(trade, tf_windows)
        token_estimate = _token_estimate(xml)

    if trim_applied:
        sections["trim_applied"] = True

    return {"xml": xml, "token_estimate": token_estimate, "sections": sections}


# ---------------------------------------------------------------------------
# Strategy dossier (Task C3b, CT-7 / research doc §4)
# ---------------------------------------------------------------------------

# §4 tools note, included verbatim after </documents> (research doc §4: the
# actual `get_trade_bars`/`get_trade_detail` tool DEFINITIONS go in the API
# request's `tools=[...]`, not in prompt text -- this comment documents the
# intent for the caller assembling the request).
_STRATEGY_TOOLS_NOTE = (
    "<!-- cache_control breakpoint at the end of </documents>. Declare get_trade_bars and\n"
    "     get_trade_detail as real Claude API tool definitions (tools=[...]), not prompt text --\n"
    "     capped at 25,000 tokens/response per Anthropic's own Claude Code default (RQ7). Keep the\n"
    "     tool set identical across turns of the same review session -- adding/removing a tool\n"
    "     invalidates the cached data block too (RQ6/RQ8). -->"
)


def _fetch_variants(db_path: Path, strategy_id: str) -> list[dict[str, Any]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM variant WHERE strategy_id=? ORDER BY variant_seq ASC",
            (strategy_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _metrics_block_text(label: str, block: dict[str, Any] | None) -> str:
    """One CT-3 scorecard metrics block (`real`/`teorico`) -> plain-text
    stats lines (server-computed, never left for the model -- research doc
    §4/§RQ5)."""
    if block is None:
        return f"{label}: n/a (no data)"
    window = block.get("window") or {}
    wr = block.get("wr")
    wr_pct = wr * 100.0 if wr is not None else None  # metrics.wr is [0,1]
    lines = [
        f"{label}:",
        f"  Period: {window.get('from') or 'n/a'} to {window.get('to') or 'n/a'} | N trades: {block.get('trades')}",
        f"  Net: {_fmt(block.get('net'), 2)} | Profit factor: {_fmt(block.get('pf'), 2)} | "
        f"Win rate: {_fmt(wr_pct, 1)}% | Payoff: {_fmt(block.get('payoff'), 2)}",
        f"  Expectancy (R): {_fmt(block.get('expectancy_r'), 3)}"
        + (f" [{block.get('expectancy_r_flag')}]" if block.get("expectancy_r_flag") else ""),
        f"  Net/day: {_fmt(block.get('net_per_day'), 2)} | Trades/day: {_fmt(block.get('trades_per_day'), 2)} | "
        f"MaxDD: {_fmt(block.get('maxdd_pct'), 2)}% | Sharpe(d): {_fmt(block.get('sharpe_d'), 2)}",
    ]
    return "\n".join(lines)


def _aggregate_stats_section(scorecard: dict[str, Any]) -> str:
    floors = scorecard.get("floors") or {}
    lines = [
        f"Metrics contract: {scorecard.get('metrics_contract')} | "
        f"Baseline ref: {scorecard.get('baseline_ref') or 'n/a'}",
        _metrics_block_text("Real (forward/live)", floors.get("real")),
        _metrics_block_text("Teorico (baseline backtest)", floors.get("teorico")),
    ]
    return "\n".join(lines)


def _strategy_record_section(strategy: dict[str, Any], variants: list[dict[str, Any]]) -> str:
    """Small, irregular structure -> compact JSON (research doc §RQ1/§RQ8),
    same hand-rolled deterministic style as `_trade_record_section`."""
    var_lines = []
    for v in variants:
        var_lines.append(
            "    {"
            f'"variant_id": "{v["variant_id"]}", '
            f'"tf": "{v.get("tf") or "n/a"}", '
            f'"instrumento": "{v.get("instrumento") or "n/a"}", '
            f'"modo_salida": "{v.get("modo_salida") or "n/a"}"'
            "}"
        )
    variants_json = "[\n" + ",\n".join(var_lines) + "\n  ]" if var_lines else "[]"
    lines = [
        "{",
        f'  "strategy_id": "{strategy["strategy_id"]}",',
        f'  "name": "{strategy.get("name")}",',
        f'  "familia": "{strategy.get("familia")}",',
        f'  "platform": "{strategy.get("platform")}",',
        f'  "estado": "{strategy.get("estado") or "n/a"}",',
        f'  "graduated": {"true" if strategy.get("graduated") else "false"},',
        f'  "notes": "{strategy.get("notes") or ""}",',
        f'  "variants": {variants_json}',
        "}",
    ]
    return "\n".join(lines)


def _runs_table(runs: list[dict[str, Any]]) -> str:
    header = (
        "| run_id | variant_id | engine | fidelity | periodo | trades | net | pf | wr | maxdd | sharpe |"
    )
    sep = "|--------|------------|--------|----------|---------|-------:|----:|---:|---:|------:|-------:|"
    rows = [header, sep]
    for r in runs:
        periodo = f"{r.get('periodo_desde') or 'n/a'}..{r.get('periodo_hasta') or 'n/a'}"
        rows.append(
            f"| {r['run_id']} | {r.get('variant_id') or 'n/a'} | {r.get('engine') or 'n/a'} | "
            f"{r.get('fidelity') or 'n/a'} | {periodo} | {r.get('trades') if r.get('trades') is not None else 'n/a'} | "
            f"{_fmt(r.get('net'), 2)} | {_fmt(r.get('pf'), 2)} | {_fmt(r.get('wr'), 1)} | "
            f"{_fmt(r.get('maxdd'), 2)} | {_fmt(r.get('sharpe'), 2)} |"
        )
    return "\n".join(rows)


def _render_strategy(
    strategy: dict[str, Any],
    variants: list[dict[str, Any]],
    scorecard: dict[str, Any],
    runs: list[dict[str, Any]],
) -> tuple[str, dict[str, int]]:
    """§4 template order: aggregate stats FIRST (stats-first, research doc
    §4/§RQ5), then the strategy/variants record, then the compact
    one-row-per-run recent-runs table. Tools note appended verbatim after
    </documents> (§4)."""
    sid = strategy["strategy_id"]
    sections: dict[str, int] = {}

    stats_content = _aggregate_stats_section(scorecard)
    sections["aggregate_stats"] = len(stats_content)

    record_content = _strategy_record_section(strategy, variants)
    sections["strategy_record"] = len(record_content)

    runs_content = _runs_table(runs)
    sections["recent_runs"] = len(runs_content)

    docs = [
        _document(1, f"aggregate_stats:{sid}", stats_content),
        _document(2, f"strategy_record:{sid}", record_content),
        _document(3, f"recent_runs:{sid}:n={len(runs)}", runs_content),
    ]
    xml = (
        "<documents>\n\n" + "\n\n".join(docs) + "\n\n</documents>\n\n"
        + _STRATEGY_TOOLS_NOTE
    )
    return xml, sections


def build_strategy_dossier(
    strategy_id: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Build the strategy-review dossier for `strategy_id` per CT-7 / §4.
    Returns `{"xml": str, "token_estimate": int, "sections": dict[str, int]}`.

    Sources (all read-only, in-process -- NEVER an HTTP self-call):
      - strategy + variant rows from the registry DB,
      - CT-3 scorecard via `sentinel_engine.research.scorecard.build_scorecard`
        (the SAME internals the scorecard endpoint uses),
      - recent runs via `ResearchRegistry.query_runs` (newest first).

    Budget: <= `BUDGET_TOKENS_STRATEGY` (10K) estimated tokens; if over,
    the recent-runs table is trimmed by dropping its OLDEST rows (bottom of
    the newest-first table), recorded via `sections["trim_applied"]`.
    """
    from sentinel_engine.research.registry2 import ResearchRegistry
    from sentinel_engine.research.scorecard import build_scorecard

    db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    registry = ResearchRegistry(db_path)

    strategy = registry.get_strategy(strategy_id)
    if strategy is None:
        raise DossierError(f"unknown strategy_id: {strategy_id!r}")

    scorecard = build_scorecard(registry, strategy_id)
    if scorecard is None:  # pragma: no cover -- get_strategy already guarded
        raise DossierError(f"unknown strategy_id: {strategy_id!r}")

    variants = _fetch_variants(db_path, strategy_id)
    runs = registry.query_runs(
        strategy_id=strategy_id, limit=RECENT_RUNS_LIMIT,
    )["rows"]

    xml, sections = _render_strategy(strategy, variants, scorecard, runs)
    token_estimate = _token_estimate(xml)

    trim_applied = False
    # Same trim discipline as the position dossier: bulk-drop the OLDEST
    # rows (bottom of the newest-first runs table) based on average
    # chars/row, re-render, re-measure -- converges in O(few) passes.
    while token_estimate > BUDGET_TOKENS_STRATEGY and len(runs) > 1:
        excess_chars = (token_estimate - BUDGET_TOKENS_STRATEGY) * CHARS_PER_TOKEN
        avg_row_chars = max(1.0, sections.get("recent_runs", len(runs) * 60) / max(1, len(runs)))
        drop_n = max(1, min(len(runs) - 1, int(excess_chars / avg_row_chars) + 1))
        runs = runs[: len(runs) - drop_n]
        trim_applied = True
        xml, sections = _render_strategy(strategy, variants, scorecard, runs)
        token_estimate = _token_estimate(xml)

    if trim_applied:
        sections["trim_applied"] = True

    return {"xml": xml, "token_estimate": token_estimate, "sections": sections}
