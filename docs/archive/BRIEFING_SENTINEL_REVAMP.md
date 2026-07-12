# SENTINEL — System Briefing & Revamp Design Brief

> **What this document is.** A complete, neutral, source-derived description of the SENTINEL trading-intelligence system **as it exists today**, followed by an objective specification of the **changes and extensions we intend to make**. It is written to be handed to a single model (Fable 5) as a one-shot prompt.
>
> **Reference state.** Version `3.7.1` (codename "AI Advisor"), branch `release`, latest commit `6ee5310`. All facts in Part A are derived from direct reading of the source (`sentinel/*.py`, `config.py`, `README.md`, git state). Where the README and the code disagree, the **code is authoritative** and the discrepancy is flagged.
>
> **Security note.** Broker credentials that exist in the working tree (a plaintext MT5 demo password in an untracked `CUENTAS.md`) are deliberately excluded from this document.

---

## HOW WE NEED YOU (FABLE 5) TO RESPOND

Read this brief in full, then produce your answer as **one single deliverable**: **one `.md` file** containing **all** of the response sections requested in **Part I**.

Requirements on that deliverable:

- **Extensive and detailed.** Do not summarize away substance. Cover every request in Part I completely.
- **Concise, technically dense prose.** No filler, no restating the brief back to us, no motivational padding, no hedging boilerplate. Every sentence should carry engineering information.
- **Nothing left in the inkwell.** Do not omit any detail, edge case, alternative, risk, or trade-off you have considered. If you weighed an option and discarded it, say so and say why.
- **General → technical.** Give the high-level recommendation first, then the technical specifics that make it actionable.
- **Neutral and evidence-based.** Present alternatives with trade-offs; state your recommendation and the reasoning behind it.

**Interaction budget.** You get essentially **one shot**. If — and only if — you are missing information that is genuinely blocking a correct answer, you may ask us for it **once**, as a single, complete, explicit, itemized list of exactly what you need; we will answer and you get **one** more run. That is the maximum. Do not burn the follow-up on nice-to-haves; assume reasonable defaults for anything non-blocking and state the assumption.

**Scope boundary for this one-shot.** This request is about the **objective design of the whole system and how to implement it now** — architecture, the backtesting/optimization engine, the AI-assistant and replay/logging extensions, and an implementation plan. The **exhaustive, indicator-by-indicator tuning proposal** (specific weights, thresholds, per-signal recommendations) is **explicitly out of scope** here and will be requested in a **separate dedicated one-shot** later. In this document, when we ask about strategies/EAs, we want **brief descriptions of the most evident best options only, no code.**

---

# PART A — CURRENT SYSTEM (BASELINE)

## A.1 Purpose

SENTINEL is a real-time analysis panel originally built for the **USD/CLP** pair, oriented to scalping (1–30 minute trades), delivered as a **local web app built with Streamlit**. It connects to **MetaTrader 5 (broker Capitaria)** for live prices and candles, with **Yahoo Finance** as fallback. **It does not execute orders** — it is read-only/analysis; MT5 calls are limited to reading prices/candles/deal history (`symbol_info_tick`, `copy_rates_from_pos`, `symbol_select`, `history_deals_get`).

The system fuses:
- A **multi-timeframe technical score** (EMA, RSI, MACD, Bollinger Bands, price action).
- A **macro / cross-asset score** (correlation of the target vs. a basket of related instruments).
- **Support/resistance levels** (Camarilla pivots + swing detection).
- A **backtester** that replays the scoring over historical data and compares it against the trader's real trades.
- A **conversational AI assistant** (Anthropic Claude) that receives a full snapshot of the dashboard.

Recent commits extended it beyond USD/CLP: a second dashboard (`dashboard_v2.py`) adds equivalent panels for **NASDAQ100 (`NQ100`)** and **Gold (`XAUUSD`)**, reusing the same scoring architecture with per-instrument correlation tables and weights.

## A.2 Architecture & data flow

```
SENTINEL.bat (Windows, double-click)
   └─▶ sentinel/launcher.py         (self-contained bootstrap/updater)
          └─▶ streamlit run sentinel/app.py
                 ├─ "/"   → dashboard.py       (v1 — USD/CLP, production)
                 └─ "/v2" → dashboard_v2.py    (v2 — USD/CLP + NASDAQ100 + Gold)

MT5 / Yahoo Finance
   ▼
DataFeed (data_feed.py)      ← abstracts source, caches, normalizes OHLCV
   ├──▶ SentinelCore         ← orchestrates composite score (v1, USD/CLP)
   │       ├── TechnicalScorer    → multi-TF technical score
   │       ├── MacroScorer        → EWMA cross-asset macro score
   │       ├── CorrelationEngine  → "legacy" correlation score + divergences
   │       └── LevelsEngine       → S/R levels
   ├──▶ MacroScorer (extra instances) + instrument_panel.render_panel
   │       → NASDAQ100 & Gold panels in dashboard_v2.py
   ▼
Dashboard (dashboard.py / dashboard_v2.py)   ← renders UI, periodic refresh
```

**Refresh model (critical for Part C).** Each Streamlit page runs as a **full script re-execution on every refresh** (standard Streamlit pattern): at the end of the script, if auto-refresh is on, it does `time.sleep(DASHBOARD_REFRESH_SECONDS)` then `st.rerun()`, restarting the entire script. `DASHBOARD_REFRESH_SECONDS = 1.5`. Everything — every score, every correlation, every indicator, the whole DOM — is recomputed and re-rendered every 1.5 s.

## A.3 Entry point & bootstrap

**`launcher.py`** (820 lines) is a self-contained bootstrap (no host PATH/registry changes) running 8 logged steps: (1) `check_running` (probes `localhost:8501`), (2) `check_python` (requires 3.11–3.13; else finds or downloads an **embedded portable Python 3.12.8** into `_python/` and relaunches), (3) `check_git` (system git or portable MinGit 2.47.1, non-blocking), (4) `check_updates` (`git pull` on `release`, else clone+copy, else GitHub ZIP; preserves `chat_history/` and `__pycache__/`; self-relaunches if the launcher's own MD5 changed), (5) `check_deps` (MD5-marker cache; imports key packages; `pip install -r requirements.txt`, 900 s timeout), (6) `verify_imports`, (7) `verify_dashboard`, (8) `launch` (`streamlit run sentinel/app.py`, opens browser after 8 s).

**`app.py`** (43 lines) is the real entry point using Streamlit's native multipage API (`st.navigation`): `init_system()` (cached with `@st.cache_resource`) creates one shared `DataFeed` + `SentinelCore` to avoid opening two MT5 connections; registers `dashboard.py` at `""` and `dashboard_v2.py` at `"v2"`.

**`SENTINEL.bat`** is the one-click Windows launcher that invokes the launcher.

## A.4 Central configuration (`config.py`)

Constants and dataclasses, no business logic. Exact current values:

- `DATA_MODE = "mt5"` (fallback `"api"`/Yahoo).
- **`SYMBOLS`** (USD/CLP + correlation basket): target `USDCLP`, dxy `USDX_Jun26`, copper `Cobre_Jul26`, wti `WTI`, usdmxn `USDMXN`, usdbrl `USDBRL`, audusd `AUDUSD`, usdcnh `USDCNH`, sp500 `SP`. `SYMBOLS_YAHOO` maps each to a Yahoo ticker.
- **`EXPECTED_CORRELATIONS`** (vs USD/CLP): dxy +0.75, copper −0.70, wti +0.40, usdmxn +0.60, usdbrl +0.55, audusd −0.50, usdcnh +0.45, sp500 −0.30.
- **Gold panel** — `SYMBOLS_GOLD` target `XAUUSD` (dxy, silver `XAGUSD`, vix `VIX_Jun26`, eurusd, sp500, usdjpy [documented "real-time proxy for US10Y yields"], copper). `EXPECTED_CORRELATIONS_GOLD`: dxy −0.70, silver +0.85, vix +0.35, eurusd +0.45, sp500 −0.15, usdjpy −0.60, copper +0.30. `ASSET_WEIGHTS_GOLD`: dxy 3.0, silver 2.5, usdjpy 2.5, eurusd 1.5, vix 1.0, sp500 1.0, copper 1.0.
- **NASDAQ panel** — `SYMBOLS_NASDAQ` target `NQ100` (sp500, vix, dxy, usdjpy, bitcoin `BTCUSD`, wti, eurusd, gold). `EXPECTED_CORRELATIONS_NASDAQ`: sp500 +0.92, vix −0.80, dxy −0.50, usdjpy +0.45, bitcoin +0.55, wti −0.35, eurusd +0.35, gold −0.15. `ASSET_WEIGHTS_NASDAQ`: sp500 3.0, vix 3.0, dxy 2.5, usdjpy 2.0, bitcoin 1.5, wti 0.7, eurusd 1.0, gold 0.5.
- **`TIMEFRAMES`**: M1=1, M2=2, M5=5, M15=15 min. `BARS_TO_FETCH = 200`.
- **`RiskConfig` (`RISK`)**: capital 1,500,000 CLP; risk/trade 1%; max daily loss 3%; max 3 trades/day; min R:R 1.5; ATR SL ×2.0, ATR TP ×3.0; pause after 2 consecutive losses for 120 min.
- **`ScoreWeights` (`WEIGHTS`)**: `technical = 0.50`, `correlation = 0.50`. **(README documents 75/25 — that is an older version; the code runs 50/50.)**
- **Thresholds**: `SCORE_ALERT_THRESHOLD = 65`, `SCORE_STRONG_THRESHOLD = 75`.
- **`IndicatorParams` (`INDICATORS`)**: EMA 9/21/50/200; RSI 14 (OB 70 / OS 30); MACD 12/26/9; BB period 20, std 2.0; ATR 14.
- **Correlation**: `CORRELATION_WINDOW = 50`, `CORRELATION_BREAK_THRESHOLD = 0.3`, `DIVERGENCE_THRESHOLD = 0.02` (2%).
- **Session (CLT/UTC-4)**: open 09:30, primary close 14:00, hard close 15:30, `NEWS_BUFFER_MINUTES = 30`.
- `DASHBOARD_REFRESH_SECONDS = 1.5`, `DASHBOARD_LANGUAGE = "es"`. Paths: `BASE_DIR`, `DATA_DIR`, `JOURNAL_PATH = data/trades_journal.csv`.

## A.5 Data feed (`data_feed.py`, 307 lines)

`DataFeed(mode="auto")` — the single unified, **read-only** market-data layer. The module docstring and inline comments assert read-only intent explicitly (only `symbol_info_tick`, `copy_rates_from_pos`, `symbol_select`, `account_info`, `terminal_info` are ever called; no order functions are imported).

- **Connection.** On init (`mode ∈ {auto, mt5}`) calls `_try_connect_mt5()`: `import MetaTrader5`, `mt5.initialize()`, validates `account_info()` **and** `terminal_info()`; on success sets `mt5_connected=True`, `mode="mt5"`, logs login/server/build and `trade_allowed`, and **dynamically populates a module-global** `MT5_TIMEFRAMES` dict mapping minutes→MT5 constants (1→M1, 2→M2, 5→M5, 15→M15, 30→M30, 60→H1, 240→H4, 1440→D1). If MT5 import/init fails it silently degrades to `mode="yfinance"`. `ImportError` is handled distinctly from runtime errors.
- **`_enable_symbols()`** unions the values of `SYMBOLS ∪ SYMBOLS_GOLD ∪ SYMBOLS_NASDAQ` and calls `symbol_select(sym, True)` for any not yet `visible` in Market Watch — this is why one `DataFeed` serves all three instrument families.
- **`get_data(symbol, timeframe_minutes=15, bars=200)`** → OHLCV DataFrame indexed by `time`. **Cache** keyed `f"{symbol}_{tf}_{bars}"` with TTL **5 s (MT5)** / **30 s (Yahoo)**; only **non-empty** frames are cached. Tries `_get_data_mt5` (`copy_rates_from_pos(symbol, tf, 0, bars)`, renames `tick_volume`→`volume`, falls back to `real_volume`, forces the `[open,high,low,close,volume]` schema) and, if empty, `_get_data_yfinance`.
- **`_get_data_yfinance`** maps symbol→Yahoo ticker via a **broader** `YAHOO_TICKERS` table than `config.SYMBOLS_YAHOO` — it also covers Gold/NASDAQ cross-assets (`XAUUSD→GC=F`, `XAGUSD→SI=F`, `NQ100→^NDX`, `BTCUSD→BTC-USD`, `VIX_Jun26→^VIX`, `EURUSD→EURUSD=X`, `USDJPY→JPY=X`). Intervals `YF_INTERVALS` (1→"1m", 5→"5m", 15→"15m", 30→"30m", 60→"60m", 240/1440→"1d") and periods `YF_PERIODS` ("1m"→"7d", "5m/15m/30m/60m"→"60d", "1d"→"1y") bound how much history Yahoo can return — **a hard constraint for any Yahoo-sourced backtest** (e.g. M1 only goes back ~7 days). A one-shot flag prevents log flooding when `yfinance` is absent.
- **`get_current_price(symbol)`** → `{bid, ask, spread, time, source}`. Live from `symbol_info_tick` (`source="mt5"`) when connected and `bid>0`; otherwise **synthesizes** `bid=last M5 close`, `ask=bid×1.001` (**0.1% synthetic spread**), `source="yfinance"`. Returns zeros/`source="none"` if no data — a real edge case downstream code must tolerate.
- **`get_all_data(timeframe_minutes, bars)`** iterates **only `config.SYMBOLS`** (the USD/CLP basket) — the Gold/NASDAQ panels do **not** go through this method (see A.13). `get_symbol_info`, `get_status` (mode, connection, cache size, account balance/server/build), `shutdown` (clean `mt5.shutdown()`).

## A.6 Technical indicators (`indicators.py`, 127 lines)

Thin wrapper over the `ta` library. `calculate_all(df)` (requires ≥50 rows, else returns df unchanged) appends: `ema_9/21/50` (and `ema_200`, set to `NaN` if fewer than 200 rows), `rsi` (14), `macd`/`macd_signal`/`macd_histogram` (12/26/9), Bollinger `bb_upper/middle/lower/bb_pct` (20, 2.0σ — `bb_pct` is the %B position within the bands), `atr` (14). Then derived signal columns computed vectorized:
- `ema_trend_signal`: +1 if `close>ema_50`, −1 if `close<ema_50`, else 0.
- `ema_cross`: +1 on the bar where `ema_9` crosses **above** `ema_21` (`shift(1)` comparison), −1 on cross below, else 0.
- `rsi_signal`: −1 if RSI>70, +1 if RSI<30, +0.5 in (50,70], −0.5 in [30,50).
- `macd_trade_signal`: sign of the histogram.

`get_latest_signals(df)` flattens the last row into a plain dict (`price, ema_9/21/50/200, rsi, macd*, bb_*, atr, *_signal, ema_cross`) with `.get` defaults — this dict is the **sole interface** consumed by the scorer.

## A.7 Technical score (`technical_scorer.py`, 198 lines)

`calculate_technical_score(df, normalize_macd=False)` → `{score, direction, details, signals}`. Guards return a neutral `score=50` on `<50` rows or empty signals. Composite = weighted sum of 5 sub-scores, **EMA 0.30 / RSI 0.20 / MACD 0.25 / BB 0.15 / PA 0.10**, clamped [0,100]. Direction = `LONG` if the summed integer votes `>1`, `SHORT` if `<−1`, else `NEUTRAL` (i.e. needs ≥2 net concurring indicators).
- **`_score_ema(s)`**: `85/vote+1` if `e9>e21>e50>0` (full bull), `15/−1` if `e9<e21<e50` (full bear), `65/+1` or `35/−1` if ≥2 EMAs on one side of price, else `50/0`; then **±15** and a forced vote on a fresh `ema_cross`.
- **`_score_rsi(s)`**: `30/−1` if RSI≥70 (overbought→bearish), `70/+1` if ≤30 (oversold→bullish); in between, `55+(rsi−50)×0.5` with **vote +1 above 50** and `45−(50−rsi)×0.5` with **vote −1 below 50** (note: the momentum zone still emits a directional vote, not 0).
- **`_score_macd(s, atr)`**: if `normalize_macd` and `atr>0`, `50 + (h/atr)×40` clamped (prevents saturation on high-priced instruments like USDCLP/XAUUSD where raw `h×1000` pins to 0/100); else legacy `60+|h|×1000` (h>0) / `40−|h|×1000` (h<0).
- **`_score_bb(s)`**: `bb_pct>0.95`→`25/−1`, `<0.05`→`75/+1`, `>0.7`→`40/0`, `<0.3`→`60/0`, else `50/0`.
- **`_score_pa(df)`**: candle body/range ratio; `>0.7`→`70/+1` (bull) or `30/−1` (bear); otherwise `55`(up)/`45`(down) with vote 0.

`calculate_multi_tf_score(data_feed, symbol)` fetches each TF (`BARS_TO_FETCH=200`) and scores it with **`normalize_macd=True` for ALL timeframes** (the inline comment overrides the older "M1/M2 only" behavior). Composite uses per-TF weights **`{M15:0.10, M5:0.20, M2:0.35, M1:0.35}`**. Returns `composite_score`, `h4_direction` (**= the M15 direction**, key name is legacy), `confluence` (max count of TFs agreeing on LONG or SHORT), `tf_scores`, `rsi_divergences`. **Weight-consistency note:** these live weights are 35/35/20/10; the AI-context prompt text hardcodes 40/30/20/10 and the composite formula 75/25 (A.15) — both stale relative to the running code.

`detect_rsi_divergences(tf_scores)` compares adjacent TFs in order M1→M2→M5→M15; gaps ≥10 are classified LEVE(≥10)/MODERADA(≥15)/FUERTE(≥25) with an interpretive Spanish string (overbought-vs-neutral → likely pullback, etc.), sorted by magnitude.

## A.8 Legacy cross-asset correlation engine (`correlation_engine.py`, 486 lines)

Two independent layers.

**A.8.1 Rolling-window functions (used by `SentinelCore` on H1/200-bar data).** `calculate_correlation_matrix(all_data, window=50)` copies each instrument's `close`, converts tz-aware indices to UTC-naive, **rounds timestamps to the hour**, drops duplicate hours (keep last), builds an inner-joined DataFrame, takes `log(close/close.shift(1))` returns, and returns the Pearson `corr()` of the last `window` rows (or all if fewer). `calculate_target_correlations(all_data, target_key="target")` reads the target column, and per instrument in `EXPECTED_CORRELATIONS` records `actual` (rounded 3dp), `divergence = actual−expected`, and appends a **break** + alert when `|actual|<CORRELATION_BREAK_THRESHOLD(0.3)` while `|expected|>0.4`. `_calculate_correlation_score(all_data, correlations)`: per asset a binary `±1` vote from `sign(5-bar return)` combined with `sign(expected corr)`, weighted by a **hardcoded weight table duplicated here** (dxy 3.0, copper 2.5, usdmxn/usdbrl 1.5, wti/audusd/usdcnh 1.0, sp500 0.5), normalized by total weight to `50+|consensus|×50`. `_determine_correlation_direction` uses a `DIVERGENCE_THRESHOLD(0.02)`-gated bull/bear tally (`diff>0.5`→LONG, `<−0.5`→SHORT). `detect_divergence` flags each asset where `sign(other_return × expected_corr) ≠ sign(target_return)` and `|other_return|>0.02`, sorted by magnitude — the code comments call this "the system's main competitive edge."

**A.8.2 `RealtimeCorrelationTracker`** — a 3-layer tick-by-tick confidence tracker, explicitly calibrated for a 2.5 s scalping refresh and built to fight the **Epps effect** (HF correlations decaying to 0). Per asset it maintains: **Layer 1 — dual-lambda EWMA**: fast variance (`λ_var=0.85`, ~7-tick memory) for target and asset, slow covariance (`λ_cov=0.97`, ~33-tick memory), correlation = `cov/√(var_t·var_a)` clipped [−1,1]. **Layer 2 — sign concordance**: rolling window of 60 agreement flags (for inverse-corr assets, *disagreement* counts as agreement), later EWMA-smoothed with an adaptive span. **Layer 3 — z-score breakdown**: over the spread `ret_target − expected_sign·ret_asset`, window 50, `|z|>2.0` ⇒ regime break. `get_confidence(asset)` returns a composite only after warm-up (**≥30 updates ≈ 75 s**; before that `confidence=0`): `confidence = 0.35·ewma_agreement + 0.45·concordance + 0.20·breakdown_penalty`, where `ewma_agreement = clip(directed_corr×2.5 + 0.5, 0,1)` and `directed_corr = ewma_corr × expected_sign`. `get_all_confidence()` maps it over all tracked assets. **This tracker is the shared state object both `MacroScorer` and the per-instrument panels build on.**

## A.9 EWMA macro engine (`macro_scorer.py`, 362 lines)

`MacroScorer` — the engine that actually feeds the composite's "macro 50%". Its `__init__(self)` **takes no config**: it constructs a `RealtimeCorrelationTracker(0.85, 0.97, concordance_window=60)` and reads **module-level `ASSET_WEIGHTS` + `config.EXPECTED_CORRELATIONS` + `config.SYMBOLS`, all hardwired to USD/CLP** (dxy 3.0, copper 2.5, usdmxn/usdbrl 1.5, wti/audusd/usdcnh 1.0, sp500 0.5). This is why the class is USD/CLP-only and the Gold/NASDAQ panels reimplement its math locally (A.13).
- **`update_tick(data_feed)`**: computes each asset's tick return in **bps** vs its previous stored bid and feeds `tracker.update(asset, ret_target, ret_asset, sign(expected_corr))`.
- **`calculate_score(data_feed)`**: per asset pulls EWMA `confidence`, a **recent return over the last 3 M1 bars (~3 min)** in bps, forms a directional vote `raw_vote = tanh(recent_bps / TANH_SENSITIVITY=5.0) × expected_sign` (5 bps ≈ half-saturation), an `effective_weight = confidence × base_weight`, and `weighted_vote = raw_vote × effective_weight`. `consensus = Σweighted_vote / Σeffective_weight ∈ [−1,1]`; `direction_score = 50+consensus×50` (this is the value returned as the macro **score**), `consensus_score = 50+|consensus|×50`; direction LONG/SHORT/NEUTRAL by `consensus ≷ ±0.15`. Returns per-asset `votes` (return_bps, raw/weighted vote, confidence, ewma_corr, concordance, warmup), `confidence_avg` (mean over warmed assets), `assets_warmed_up`.
- **`calculate_score_at_window(data_feed, lookback_bars=3)`**: same math over an explicit lookback (1/3/5/15 bars for the 5s/30s/1m/5m signals), with tanh sensitivity scaled by the window. Used for multi-scale signal cards.
- **`calculate_fusion(tech_score, tech_dir, macro_score, macro_dir)`**: if directions **align** (both non-neutral, equal) → average + a bounded boost `min(10, |t−50|·|m−50|/500)` toward the shared side, `confluence_pct=(t+m)/2`; if **opposed** → pull toward 50 (`50 + 0.3·(t−50) + 0.3·(m−50)`), `confluence_pct=100−|t−m|`; if one neutral → lean 0.6× toward the active one. Fusion direction by `≥60/≤40`. **Risk mode**: aligned & confluence≥80 → `AGGRESSIVE 🟢 (SL×2.0, TP×3.5)`; confluence≥50 → `NORMAL 🟡 (2.0/3.0)`; else `CONSERVATIVE 🔴 (1.5/2.0)`.

## A.10 Levels engine (`levels_engine.py`, 259 lines)

`calculate_levels(data_feed, symbol)` pulls **daily (10 bars)** for pivots, **M15 (200)** for swings, **M5 (50)** for current price (falls back to M15 close); returns `{pivot, swings, combined, current_price, position}` (or an empty structure if price is 0). `_calculate_camarilla(df_daily)` uses the **penultimate** daily row (yesterday, since today is in progress): `Range=H−L`, `PP=(H+L+C)/3`, `R1/R2/R3 = C + Range×1.1/{12,6,4}`, `S1/S2/S3 = C − Range×1.1/{12,6,4}`, plus `prev_high/low/close/range` (all rounded 2dp). `_detect_swing_levels(df, current_price, order=5)` runs `scipy.signal.argrelextrema` (5 bars each side ≈ 2.5 h on M15) on highs/lows, keeps unique rounded levels within **±5%** of price, nearest 5 per side. `_combine_levels` always injects the 6 Camarilla R/S, adds swings that aren't within 0.1% of an existing level, computes each level's `pct` distance, splits into `above`/`below`, and **backfills synthetic extrapolated levels** (step ≈ Camarilla S3/R3 spacing) to guarantee 3 per side; returns `{above[:3], below[:3], pp}`. `_interpret_position` emits a Spanish sentence keyed on price vs yesterday's high/low, R1/S1, and PP.

## A.11 Orchestrator (`sentinel_core.py`, 102 lines)

`SentinelCore(data_feed)` constructs its own `MacroScorer` and, in `calculate_composite()`, runs the full pipeline each call: (1) `calculate_multi_tf_score` → `tech_score`, `tech_dir`(=M15 anchor); (2) `macro_scorer.update_tick` then `calculate_score` → `macro_score`, `macro_dir`; (3) legacy correlation `calculate_target_correlations` + `detect_divergence` on `get_all_data(timeframe_minutes=60, bars=200)` — **kept only for the UI table and divergence alerts, explicitly NOT in the composite**; (4) `calculate_levels`; (5) **composite = `tech_score×WEIGHTS.technical + macro_score×WEIGHTS.correlation`** (50/50), clamped and rounded 1dp; (6) **consensus direction** by weighted vote **technical=2, macro=3** among LONG/SHORT/NEUTRAL (`max` of the tally); (7) traffic light `🟢 FUERTE ≥75 / 🟡 ALERTA ≥65 / 🔴 ESPERAR`; (8) alerts = score line + top-3 divergences + legacy-correlation break alerts. Returns one dict whose `components.correlation` key is **actually powered by MacroScorer** (name retained for dashboard backward-compat), with the true legacy score parked under `components._correlation_legacy` and the full macro result under `components._macro`.

## A.12 Dashboard v1 (`dashboard.py`, 1658 lines)

Streamlit UI at `/`. Structure: page config + heavy CSS injection (dark palette, hover tooltips, toolbar hiding, refresh transition animation); cached `init_system()`; sidebar (version, MT5-live vs Yahoo-delay status, cache size, auto-refresh checkbox, interval); composite computation + extra per-asset quick technical scores + rolling "HOY" correlation (30-bar M1 Pearson, expected-sign directed, scaled 0–100%) + tick-by-tick price registration in `session_state` for instant arrows; a **5-column header row**: `col_score` (v1 signal panel ⚡5s/🔄30s/📊1m/📈5m, v2 signals with price derivatives — velocity/acceleration over up to 200 bid ticks, ±25/±10 boosts — momentum bar, final Score+Direction traffic light), `col_levels` (R1–R3/S1–S3 with tooltips + live bid/ask/spread), `col_tf` (one card per TF with score/direction/RSI + 5-sub-indicator tooltip), `col_corr` (cross-asset table with tick/~2min/~5min arrows, hover SVG sparkline, "HOY" rolling confidence, ✅/⚠️/🔴 classification), `col_macro` (per-asset macro votes: bps return, weighted vote, confidence, warm-up ⏳); Alerts section; **"EXPERIMENTAL v4.0 — Triple Signal System"** (Technical/Macro/Fusion via `calculate_fusion` + confluence meter with SL/TP multipliers); an additional 4-signal experimental panel; "vote detail" expander; **Backtesting expander** (period controls → `backtester.replay_scoring`/`compare_with_trades`, dual price/score chart, per-trade table); **AI Assistant expander** (model selector Opus/Sonnet/Haiku, Web Search checkbox, API-key field, thinking-effort selector [disabled when Web Search on], persisted chat, citation rendering, cumulative cost/token counter, autosave); footer + the `sleep+rerun` refresh loop.

## A.13 Dashboard v2 & multi-instrument panels (`dashboard_v2.py` 820, `instrument_panel.py` 455 lines)

`dashboard_v2.py` at `/v2` reproduces v1's structure with a more integrated Triple Signal block and adds two lower panels — **NASDAQ100** and **Gold** — each via `instrument_panel.render_panel(...)`.

`instrument_panel.render_panel(feed, symbols_cfg, expected_corrs, asset_weights, panel_key, label, emoji)` rebuilds the full per-instrument panel (fused signal cards with price derivatives, momentum bar, macro-derivative cards, Triple-Signal/confluence, per-TF cards with 5-sub-indicator tooltips, S/R column, per-asset macro-vote table with a "HOY" rolling-Pearson-30 column). **Architecturally important:** because `MacroScorer` is hardwired to USD/CLP (A.9), this module keeps a `MacroScorer` in `session_state[f"_ms_{panel_key}"]` **only for its `.tracker` state and `.calculate_fusion`**, and **reimplements the macro math inline** in `_update_macro`/`_calc_macro` — those local copies DO honor the panel's own `expected_corrs`/`asset_weights` (tanh sensitivity 5.0, confidence×weight, consensus±0.15, identical to `MacroScorer` but parameterized per asset). It also computes price velocity/acceleration from a per-panel ≤200-tick bid buffer (`_accel_w` central-difference), and per-TF card tooltips label weights **M1 35% / M2 35% / M5 20% / M15 10%** (matching the live scorer). This inline duplication is the main mechanism by which per-asset (Gold/NASDAQ) macro scoring works today — and a key refactor target for the optimization engine, which must be able to drive **one** parameterized macro path per asset.

## A.14 Backtester (`backtester.py`, 302 lines) — CURRENT STATE

- **`fetch_historical_trades(days_back=30)`**: re-`initialize()`s MT5 and calls `mt5.history_deals_get(from, to)`, builds a DataFrame from the deal namedtuples, **filters to symbols matching `"USDCLP|CLP"`** (regex, case-insensitive), and adds `time_dt` (UTC). So today it ingests **only USD/CLP** deals, from MT5 only (not the XTB export mentioned in Part D).
- **`fetch_historical_candles(symbol, tf, bars=500)`**: instantiates a fresh `DataFeed` and delegates to `get_data`.
- **`replay_scoring(bars_back=500, progress_callback=None)`**: uses M1 as the base timeline, pre-fetches each TF once, then for `i` in `[200, 200+total)` slices each TF frame to `index ≤ m1_index[i]` (`.tail(200)`, ≥30 rows) and scores it with **`calculate_technical_score(subset)` — note `normalize_macd` defaults to `False` here, unlike the live path which uses `True`** (a fidelity gap). Composite uses `tf_w={M15:.10,M5:.20,M2:.35,M1:.35}` and `WEIGHTS`; technical direction by weighted vote; v1 signals blended (`5s=M1`, `30s=.6M1+.4M2`, `1m=.4M1+.3M2+.3M5`). Emits one row per M1 bar (`timestamp, price, score, direction, tech_score, corr_score, m1..m15_score, signal_*, m1_dir`).
- **🔴 Correctness defect (must flag to Fable):** `replay_scoring` does `from sentinel.correlation_engine import CorrelationEngine` and calls `corr_engine.calculate()`, but **`CorrelationEngine` does not exist** in `correlation_engine.py` (that module exports functions + `RealtimeCorrelationTracker`, no such class). The import is at function-body top level and **not** guarded, so the correlation branch raises `ImportError` — the current replay's macro/correlation contribution is effectively **broken/never runs as intended**. Even by design it was only a **single correlation value frozen for the whole replay** (look-ahead + staleness).
- **`compare_with_trades(replay_df, trades_df)`**: pairs deals by `entry==0`(IN)/`entry==1`(OUT) on `position_id`/`order`, finds SENTINEL's row at-or-before each entry time, and computes `accuracy_pct` (share where `direction==trade_type` **and** `score≥65`), `filter_rate_pct` (losing trades where SENTINEL said wait/opposed ÷ total losers), plus a per-trade table with match/go/result glyphs.

**Limitations vs. Part D:** it only *replays vs. real trades*; **optimizes nothing**; correlation path is **broken** and, even if fixed, was **frozen/leaky**; **USD/CLP-only** and **MT5-only** for trades; **replay fidelity differs from live** (`normalize_macd=False`); runs **inside Streamlit on demand**; **no walk-forward / train-test split / overfitting control**; **no per-asset config**; and produces **no persisted, comparable report** across parameter variants. It is a starting point, not the engine Part D describes.

## A.15 AI assistant (`ai_chat.py`, 620 lines) — CURRENT STATE

- **`ModelConfig` + `MODELS`** (3 tiers, all fields hardcoded): `opus` = `claude-opus-4-7`, ≤16384 tok, $5/$25 per Mtok, `supports_thinking=True`, `thinking_effort="xhigh"`; `sonnet` = `claude-sonnet-4-6`, ≤8192, $3/$15, thinking `high`; `haiku` = `claude-haiku-4-5-20250315`, ≤8192, $0.80/$4, **no** extended thinking. A `THINKING_EFFORTS=["xhigh","high","medium","low"]` list allows manual override. **These IDs and the effort roster are stale vs. current Anthropic models — a first-class task for Part E is making this roster trivially updatable to the latest families/effort levels.**
- **`WEB_SEARCH_TOOL`**: Anthropic server tool `web_search_20250305`, `max_uses=5`, `allowed_domains` = 15 finance/Chile outlets (reuters, bloomberg, investing, forexfactory, bcentral.cl, dailyfx, tradingview, cnbc, marketwatch, fxstreet, kitco, economiaynegocios.cl, df.cl, emol.com, cooperativa.cl), `user_location` = Santiago/CL. Cost `WEB_SEARCH_COST_PER_1K=$10`.
- **`build_market_context(result, price_info, derivative_data, cross_asset_data, cross_corr_hoy, web_search_enabled)`**: assembles a large Spanish system prompt = role rules + a full dashboard snapshot: price bid/ask/spread; composite; **per-TF block** (score, dir, RSI, the 5 sub-scores, ema9/21/50, macd_h, bb_pct, ema_cross); v1 signals; price derivatives (velocity/accel/momentum/buffer); correlation lines with OK/WARN/BREAK (`|Δ|<0.2 / <0.4 / else`) + "HOY" %; recent cross-asset bps; S/R ladder with the live price marker and position text; top-3 RSI and cross-asset divergences; up to 5 active alerts; and (if web search on) a proactive-search instruction block. **🟠 Fidelity defect:** the prompt hardcodes the header **"fórmula: Tech×0.75 + Corr×0.25"** and **"TIMEFRAMES (M1=40%, M2=30%, M5=20%, M15=10%)"** — both **disagree with the running code** (50/50 composite; 35/35/20/10 TF weights). The assistant is therefore being told a model of the system that no longer matches reality; the context builder must be regenerated from the single source of truth.
- **Persistence**: `save/load/list_conversation` → JSON in `sentinel/chat_history/` (git-excluded, launcher-preserved; `list` returns newest-20).
- **`UsageTracker`** (dataclass): accumulates in/out tokens, web searches, per-query USD cost (token pricing + `$10/1000` searches), and a formatted `get_summary()`.
- **`SentinelAI`**: wraps `anthropic.Anthropic` keyed by `ANTHROPIC_API_KEY` (env **or** `set_api_key` from the UI); **mock mode** returns a "configure your key" message when absent. `chat(user_message, model_key, system_prompt, conversation, web_search_enabled, thinking_effort_override)` builds `messages`, then enables **either** `tools=[WEB_SEARCH_TOOL]` **or** `thinking={"type":"enabled","effort":…}` (mutually exclusive per API), parses text + dedup'd citations, counts `server_tool_use.web_search_requests`, records cost, and returns a rich dict (content, citations, tokens, cost, duration, error).

**Current status:** the assistant is wired but effectively **dormant / not in active use** (mock mode without a key). Re-enabling it with a live key **and** substantially expanding it (full live signal+trade context, mid-chat model/effort switching, optional auto per-trade chat on position open, news-countdown notifications) is a full revamp axis — see **Part E**.

## A.16 Diagnostics (`check_state.py`)

Standalone script: instantiates `DataFeed` + `SentinelCore`, runs `calculate_composite()` once, prints price/score/per-TF/correlations/levels/first-5-alerts. Fast full-pipeline check without the dashboard.

## A.17 Version & repo layout

`version.py`: `VERSION = "3.7.1"`, `CODENAME = "AI Advisor"`. Layout: `sentinel/` (all code + `chat_history/`), `data/` (`trades_journal.csv`), `MT5_Portable/` (portable terminal), `MT5_Tester/`, `MT5_Tester_2/` (extra MT5 instances for headless/tester use), `_python/` (embedded portable Python), `temp/` (launcher logs per OS). **README is partially stale** (omits `app.py`, `dashboard_v2.py`, `macro_scorer.py`, `instrument_panel.py`; documents composite as 75/25 vs the running 50/50). The mass `git diff` across `.py` files is **CRLF↔LF only**, not content.

---

# PART B — REVAMP CONTEXT & MOTIVATION

## B.1 Deployment reality

- **Fully local, per trader.** Each trader runs **their own** SENTINEL instance (UI + all scripts + MT5 terminal) on **their own** machine. There is no central server. Everything — dashboard, scoring, data feed, and any future backtesting UI — currently executes on the trader's laptop.
- **Target hardware (representative low-end laptop):** ~**4–6 GB RAM**, CPU with **4 threads**, **Windows 10**, **SSD** (with only ~**50 GB free** — relevant if the new stack needs an install/handoff step to free space). No dedicated GPU. MT5 runs concurrently on the same machine.
- **Connectivity:** stable internet is available.

## B.2 The two problems the traders reported

1. **The current UI is too heavy for the target hardware.** Symptoms: the UI runs **slow/laggy**, and — critically — it can **display different things to different traders** (state inconsistency across instances). We want it to run **at least noticeably better** than today on the target machines, **without becoming slower** and **without changing what it recommends or how it computes those recommendations** (the technical/macro logic must be preserved exactly). No degradation of service level.

2. **The traders want the recommendations themselves optimized via backtesting.** This is the **single most important** current request: use backtesting to **validate and optimize every indicator and signal present in the UI, per asset**, to find the parameterization that would have produced the most accurate recommendations — i.e., the settings that, if followed, would have generated the **highest profit / income and the lowest losses**. This is much larger than "tuning two weights" — see Part D.

## B.3 Governing principle

**Preserve the service level. Do not change *what* the system recommends or *how* it reasons technically. Make it lighter and more consistent; make its parameters optimizable; extend it — without regressions.**

---

# PART C — AXIS 1: LIGHTEN THE STACK (WITHOUT CHANGING BEHAVIOR)

## C.1 What makes it heavy today

- **Full-script re-execution every 1.5 s** (Streamlit `sleep + st.rerun()`): the entire pipeline (technical multi-TF, macro EWMA, legacy correlation on 200 H1 bars, S/R, all cross-asset quick scores) and the **entire DOM** (1658-line v1 page; v2 adds two more full panels) are recomputed and re-rendered on every tick.
- **Browser + Streamlit runtime + Python + MT5** all resident simultaneously on a 4–6 GB machine.
- Heavy **CSS/HTML string building** and per-refresh recomputation of derived structures (sparklines, tooltips, arrow buffers up to 200 ticks).

## C.2 Suspected consistency issue (state divergence)

Traders see *different things*. Likely contributors to characterize/confirm: Streamlit `session_state` + `@st.cache_resource` semantics under continuous rerun; per-instance cache TTLs (5 s MT5 / 30 s Yahoo) producing different snapshots; the once-at-start frozen correlation in some paths; race between the tick buffer and rerun. **The redesign must make identical inputs yield identical displayed state.**

## C.3 Invariants (must hold after any stack change)

- **Identical outputs:** same scores, same directions, same signals, same levels, same numbers as the current code for the same inputs. The scoring modules (`technical_scorer`, `macro_scorer`, `correlation_engine`, `levels_engine`, `sentinel_core`, and all of `config.py`) are the **behavioral contract**; preserve their semantics exactly (refactor/port allowed, redefine forbidden).
- **Not slower:** end-to-end perceived latency must be ≤ today's, ideally much better.
- **Local, offline-capable install** on Windows 10, ~50 GB free SSD, 4–6 GB RAM, 4 threads.
- **Free/open-source tooling only** (see Part H).

## C.4 Open design questions for you

Recommend, with concrete candidates and trade-offs and a migration-effort estimate: whether to (a) keep Streamlit but eliminate full-rerun cost (partial rendering, fragments, diff-based updates, decoupled compute loop), (b) move to a **native desktop app** (acceptable to us if not overly complex and iterable with your help — e.g., a Python-native GUI, a Tauri/Electron-style shell fed by a local Python compute service, a local web server + lightweight frontend), or (c) another architecture. Address: how to guarantee **state consistency**; how to keep the compute loop running independently of rendering; how to preserve the exact scoring contract; packaging/install on the target machine given the 50 GB constraint; and whether the compute core should be extracted into a headless engine reusable by both the UI and the backtester (Part D).

---

# PART D — AXIS 2: BACKTESTING & OPTIMIZATION ENGINE (CORE OF THIS REQUEST)

This is the **center of gravity** of the project. The current `backtester.py` (A.14) is only a starting point; we need a real **backtesting & parameter-optimization engine**. Treat everything below as scope to design **exhaustively** — surface every lever, alternative, problem, strength, and blind spot.

## D.1 Primary objective

For **each target asset independently** (currently **`NQ100`** and **`XAUUSD`**; USD/CLP historically, occasional NQ100), find — **via backtesting** — the **exact parameterization** of the recommendation system (both **technical** and, especially, **macro**) that would have produced the **most accurate/profitable** recommendations: those that, if followed, maximize profit/income and minimize losses. **Per-asset optimization is central** and explicitly required (macro correlations, expected signs, and asset weights differ per asset — see A.4).

## D.2 The full lever inventory (what "optimize" spans)

Everything below is a candidate tunable. Enumerate and reason about all of it:

- **Composite weights**: `WEIGHTS.technical` / `.correlation` (currently 50/50), and the direction-vote weights (technical 2 / macro 3).
- **Technical sub-weights**: EMA 30 / RSI 20 / MACD 25 / BB 15 / PA 10; and the per-TF blend weights (M1/M2/M5/M15) — **note the existing inconsistency in A.7**, which optimization should also resolve.
- **Indicator parameters**: EMA 9/21/50/200, RSI 14 + OB/OS 70/30, MACD 12/26/9, BB 20/2.0, ATR 14.
- **Thresholds**: `SCORE_ALERT_THRESHOLD 65`, `SCORE_STRONG_THRESHOLD 75`; correlation `WINDOW 50`, `BREAK_THRESHOLD 0.3`, `DIVERGENCE_THRESHOLD 0.02`.
- **Macro engine**: per-asset `EXPECTED_CORRELATIONS_*`, `ASSET_WEIGHTS_*`, EWMA lambdas (var 0.85 / cov 0.97), sign-agreement window (60), break window/threshold (50 / 2.0), warm-up (30).
- **Fusion & risk**: `calculate_fusion` confluence logic and the suggested ATR SL/TP multipliers; `RiskConfig` (ATR SL ×2.0, TP ×3.0, R:R 1.5, etc.).
- **Timeframe set** itself (which TFs, their weights).

## D.3 Ground truth & data available

- **Real trades, per trader** (each trader = a distinct account, so trades are attributable). Sources: **direct export from XTB** (being exported now) **and** a local **MT5 history CSV**. The exact per-trade field schema is **not yet confirmed** (expected: entry/exit timestamp, price, direction, volume, SL/TP used, PnL, symbol, commission/swap — to be verified). Instruments actually traded: **USD/CLP → pivoted to NQ100 → now XAUUSD, with occasional NQ100.**
- **Historical price**: MT5/Capitaria + internet downloads. Via **Dukascopy**: **NQ100 history back to 2024-01 and earlier**; **the same must be done for XAUUSD**. For the replay/logging module (Part F) we need history for **all instruments**, i.e. the tradable targets (USDCLP, XAUUSD, NQ100) **and** every macro/cross-asset instrument feeding their scores.
- **Macro series**: the cross-asset instruments used by `MacroScorer` (DXY, VIX, silver, yields-proxy usdjpy, sp500, copper, bitcoin, eurusd, etc.) — historical availability/source to be confirmed; must be aligned to the target's timeline for replay.
- **"Good trade" definition — left open for you to formalize.** Traders' working intuition: a good setup is when composite technical **and** macro both endorse, price has distance to buy/sell zones, and is below/above the relevant moving averages and Supertrend as appropriate — i.e., technical observation and macro signals *both* endorse the position. **But the operative truth is: the good trades are the ones that generate the most income and the fewest losses.** Reconcile these two definitions (signal-endorsement vs realized-PnL) and propose the objective function(s).

## D.4 Beyond parameter tuning — the broader study the traders want

The request opens into a larger research program. Design for all of it:

- **Per-trader trade analysis & clustering.** Ingest each trader's real trades; **group them by "trade type" / by the market regime at the time** (roughly: where the market was heading then); review **trends per group**.
- **Optimal stop-loss study.** Per group, determine the **automatic stop-loss configuration** that would have yielded the **fewest losses / most gains**. Then repeat the same analysis for **take-profit**.
- **Derived strategies / EAs.** From the optimal SL/TP findings, describe candidate **strategies / Expert Advisors** that would apply them. *(In this one-shot: brief descriptions of the most evident options only, no code.)*
- **Feed the findings back into the UI.** Use this research to **improve the live recommendations** (e.g., regime-aware SL/TP suggestions, better thresholds).
- **Macro regime conditioning (high priority).** The macro layer should ultimately gain **conditional levers — both mathematical and programmatic** — to correctly describe the **"macro market type" of the day**, per asset: **bull, bear, war, major news on the symbol (per-symbol basis)**, and more. Optimization and the recommendation logic should be able to switch behavior by regime.
- **Statistical model comparison.** Be able to **statistically evaluate which configuration/weighting is more convenient/profitable** across variants, timeframes, and regimes.

## D.5 The "edges" (aristas) — dilemmas to resolve explicitly

Address each, with your recommended resolution:

- **Objective metric.** Which target(s) to optimize: realized PnL, win-rate, profit factor, max drawdown, R-multiple, `filter_rate_pct`, or score-accuracy — we accept your recommendation on top of "lower loss / higher profit / score accuracy." How to combine multiple objectives (Pareto, weighted, constrained).
- **Overfitting / data-snooping** across a large lever space and limited trade samples: walk-forward, purged/embargoed cross-validation, out-of-sample holdout, parameter-stability preference, regularization, deflated Sharpe.
- **Look-ahead / leakage.** The current replay freezes correlation once at the start — a leakage/realism defect to fix. Guarantee every point-in-time score uses only information available then (including correct macro alignment, warm-up handling, and no future bars).
- **Regime dependence.** Per-regime vs global fitting; how to avoid a config that only fits one regime; how the regime-conditioning of D.4 interacts with optimization.
- **Ground-truth definition.** Signal-endorsement vs realized-PnL (D.3); how to label when trades are sparse; synthetic labeling from forward returns vs real trades; per-trader idiosyncrasy vs asset-level truth.
- **Sample size per trader / per asset / per regime**; pooling vs per-account fitting; statistical significance and confidence.
- **Transaction realism.** Spread (variable), slippage, commission/swap, session hours (09:30/14:00/15:30 CLT), news buffers.
- **Multi-asset generalization.** Per-asset configs are required, but decide what should stay shared vs asset-specific, and how to prevent config sprawl.
- **Search method.** Grid vs random vs Bayesian/TPE vs evolutionary vs coordinate descent — recommend per lever group, given the compute budget (D.6).
- **Reproducibility & reporting.** Deterministic runs, seed control, and **persisted, comparable reports** (see D.6).

## D.6 Compute, automation & operating model

- **Where it runs:** the **heavy backtesting runs on our side** (developer/analyst machine), **not** on the traders' low-end laptops. Only the **resulting optimized parameters** ship to the UI.
- **Automation:** the engine should run **end-to-end in one pass**, unattended, and **emit reports in a correct, persisted format** so we retain a record of **how each variant / strategy performed in each timeframe** (and per asset, per regime).
- **Lifecycle:** this is the **first** run of what must become a **periodic/continuous re-tuning process**. Deliver something **ready, tested, usable, and improvable**: the system must let this process be refined over time — explore new strategies, test different **trailing-stop-loss EAs**, add new levers — without a rewrite each time. (A later, separate one-shot will produce the exhaustive indicator-by-indicator tuning proposals; here, design the *engine and methodology* that will run them.)

---

# PART E — AXIS 3: AI ASSISTANT (RE-ENABLE & EXPAND)

The existing assistant (A.15) must be **re-enabled and significantly expanded**. We will provision an **Anthropic API account and API key**. Design for:

- **Full live context.** The chat must have, simultaneously, **all of SENTINEL's live information**: every data stream flowing through the signal system, the value of **every signal**, and **live trade info from the connected MT5** (positions opened/closed). The user converses about the current position so the assistant can **search for news that may be affecting it** and generate **deep daily analyses**, per-trade analyses, etc.
- **Model / effort switching mid-conversation.** The user must be able to switch, during the conversation, the **intelligence level and Anthropic model** used — the **full suite of effort levels for the latest version of each model family/tier**. *(Current hardcoded IDs `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20250315` are stale; the design must make the model/effort roster easily updatable to the latest Anthropic models and expose the effort-level selector cleanly. Note the current API constraint that web search and extended thinking are mutually exclusive — account for it.)*
- **Optional auto per-trade chat (toggle).** When a position is opened, **optionally** (behind a toggle) auto-launch a chat about **that specific trade** — analyze whether it merits a **dedicated** conversation; assess how it looks; search to confirm; recommend **SLs, TPs, supports, resistances, strategy, what to watch**; and flag if risk looks too high. **High priority.**
- **News countdown notifications.** Ideally surface **countdown notifications when an important news release is < X minutes/seconds away**, **without visually interfering** with the indicators/signals.

Design how this assistant layer integrates with the (possibly new) UI stack and the live compute core, how live context is assembled cheaply per turn, and how cost/effort/model selection is governed.

---

# PART F — AXIS 4: HISTORICAL REPLAY + LOGGING

Traders requested a dedicated **replay tab/window**:

- A panel with a **movable time cursor** letting them jump the market to **arbitrary, customizable days/hours, per instrument**, and **replay** from that point.
- Ability to **simulate trades with variable, controllable spread**, and to **see how the system behaved at that specific moment** — i.e., reconstruct the exact signals/scores SENTINEL would have shown then.
- This requires **having/downloading full history for all instruments**: the tradable targets (USDCLP, XAUUSD, NQ100) **and** all macro/recommendation instruments feeding them.
- Add a **historical logging module** so the system **starts logging its recommendations/scores over time** going forward (today history must be reconstructed by replay; we want native logging too).
- The replay/logging must be **compatible with testing different configurations / weights** of the signal-recommendation system, and then **statistically evaluating which is more convenient/profitable**.

This axis is tightly coupled to Part D (shared point-in-time engine, shared data, shared config-variant machinery) and to Part C (it is a UI surface that must also be light and consistent). Design the shared substrate accordingly.

---

# PART G — STRENGTHS, BLIND SPOTS & OPPORTUNITIES

Provide your own objective read, but as input, known facts:

- **Strengths:** clean separation of scoring modules; per-instrument macro parametrization already exists; read-only safety; self-contained launcher; a working (if primitive) replay+compare backtester; an AI-context builder already assembling a rich market snapshot.
- **Blind spots / fragilities to weigh (several are concrete, code-level defects found while writing this brief):**
  - **Broken backtester correlation path** — `replay_scoring` imports a nonexistent `CorrelationEngine` class → `ImportError`, unguarded (A.14).
  - **Replay ≠ live fidelity** — replay scores with `normalize_macd=False` while the live scorer uses `True` (A.14 vs A.7).
  - **Stale AI context** — the assistant's system prompt hardcodes the old 75/25 composite and 40/30/20/10 TF weights, contradicting the running 50/50 and 35/35/20/10 (A.15).
  - **`MacroScorer` is USD/CLP-hardwired** and the Gold/NASDAQ macro is a **duplicated inline reimplementation** in `instrument_panel.py` — two code paths that must be unified into one parameterized macro engine before per-asset optimization is trustworthy (A.9/A.13).
  - **Weight tables duplicated** across `macro_scorer`, `correlation_engine`, and `config` — a single source of truth is needed so optimization mutates one place.
  - **Full-rerun compute model** and **state inconsistency across instances** (C.1/C.2); no decoupled compute loop.
  - **Yahoo history limits** (M1 ≈ 7 days) constrain any fallback-sourced backtest (A.5).
  - **No overfitting control, no persisted variant reporting, no per-asset backtest config, no native historical logging, no regime awareness**; **unverified trade-data schema** (Part D); README/code drift (missing modules, wrong formula).
- **Where to look for gains** in **quality, speed, and reliability**: extracting a **headless compute core** shared by UI + backtester + replay + AI context; deterministic point-in-time evaluation; per-asset + per-regime optimization; caching/incremental compute to kill the rerun cost; a single source of truth for config variants.

---

# PART H — CONSTRAINTS, NON-NEGOTIABLES & SUCCESS CRITERIA

**Non-negotiables:**
1. **Do not change what the system recommends or how it computes it.** Scoring semantics and `config.py` meaning are the behavioral contract; lightening the stack must preserve outputs exactly.
2. **No performance regression** on the target hardware (4–6 GB RAM, 4-thread CPU, Windows 10, SSD ~50 GB free); ideally a clear improvement.
3. **Fully local** per-trader deployment; stable internet assumed but be resilient to blips.
4. **Free / open-source tooling only** for the stack and backtesting infrastructure. *(The Anthropic API used by the AI assistant is a paid runtime feature we are provisioning deliberately — that is a product capability, not "dev tooling," and is exempt from this rule.)*
5. **State consistency:** identical inputs must yield identical displayed state across instances.

**Freedoms:**
- **No technology limitations** on the stack — you may recommend anything (native desktop app is acceptable if not overly complex and iterable with our help).
- **We (a small team) maintain the system.** Integrating a genuinely new technology on a target machine may require a one-time handoff/cleanup step to free SSD space (only ~50 GB free) — factor that into install/packaging.
- **No fixed budget/deadline, but we implement immediately** — ideally the design is executable **agent-driven, today or tomorrow**. Prefer a plan that is fast, cost-effective, and high-quality, phased so we can start now.

**Success criteria:** the UI runs lighter and consistently on the target laptops with unchanged recommendations; a per-asset backtesting/optimization engine runs unattended end-to-end and emits persisted, comparable variant/timeframe/regime reports; the AI assistant and replay/logging axes have a coherent, buildable design sharing one compute core.

---

# PART I — WHAT WE ASK YOU (FABLE 5) TO DELIVER

Produce **one `.md` file**, extensive and technically dense (per "HOW WE NEED YOU TO RESPOND"), with **all** of the following sections. **Give central weight to the backtesting/optimization engine (Part D).**

1. **Stack recommendation (Part C).** Evaluate concrete candidates for lightening/rewriting the UI so it runs well on the target hardware **without changing behavior and without getting slower**. Give trade-offs, a recommendation, a migration-effort estimate, how you guarantee output-identical behavior and state consistency, how you decouple the compute loop from rendering, and packaging/install under the 50 GB constraint. Recommend whether to extract a shared **headless compute core**.

2. **Backtesting & optimization engine design (Part D) — the core.** Full architecture: data ingestion (real trades from XTB + MT5 CSV; historical price incl. Dukascopy; macro series), point-in-time (leak-free) evaluation, the complete tunable-lever treatment, per-asset (and where warranted per-regime) optimization, the objective function(s), the search method(s) per lever group, overfitting/validation strategy, transaction realism, and the persisted, comparable reporting format (per variant / timeframe / asset / regime). Include the **per-trader trade clustering, optimal SL/TP study, macro regime-conditioning (bull/bear/war/news, per symbol), and statistical model comparison**. Design it to run **unattended, end-to-end, on our machine**, as the **first iteration of a repeatable, improvable re-tuning process**.

3. **AI assistant design (Part E)** and **replay + logging design (Part F)**, each fully specified and shown sharing the same compute core / data substrate as Parts C and D.

4. **Resolution of every "edge" (D.5)** — answer each dilemma explicitly with your recommended resolution and reasoning.

5. **Strategies / EAs from optimal SL/TP (D.4)** — **brief** descriptions of the most evident best options only, **no code**.

6. **Phased implementation plan** — prioritized, cost-effective, agent-driven-executable, startable immediately, with milestones and dependencies across all four axes. (We will then use a separate step to turn your recommendations into a detailed implementation plan.)

7. **Strengths, blind spots, and every point where we can get better / faster / more reliable results (Part G)** — your objective assessment.

If — and only if — something is genuinely blocking, ask us once (single complete itemized list); otherwise assume and state reasonable defaults and deliver.
