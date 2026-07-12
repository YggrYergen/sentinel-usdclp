# XAUUSD M1 History Backfill Feasibility (2026-01-01 → 2026-03-26)

Research spec. Desk research only — no MT5 execution, no `.hcc` binary reads performed.
Question: can we backfill `D:\FOREX\data\lake\XAUUSD\1.parquet` (currently 2026-03-25 →
2026-07-07) with M1 (ideally also M2/M5/M15) bars for 2026-01-01 → 2026-03-26, needed
because an imported MT5 backtest run has trades starting 2026-01-11?

## VERDICT

**POSSIBLE.** Ranked paths below. Recommended: **Path A (read the MT5 Strategy Tester's
own terminal, which already has the Jan–Mar 2026 cache on disk, via `copy_rates_range`
over the MT5 Python API)** — the data is *already sitting on this machine* in the
standard terminal history store; it just needs to be read back out through a running
terminal + the Python API rather than treated as unreachable binary.

## Local evidence (verified this session, informs the verdict)

`D:\FOREX\MT5_Tester\Bases\Capitaria-All\history\XAUUSD\` contains:
```
2014.hcc 2015.hcc ... 2025.hcc 2026.hcc   cache
```
and `D:\FOREX\MT5_Tester\Bases\Capitaria-All\ticks\XAUUSD\` contains:
```
202601.tkc 202602.tkc 202603.tkc 202604.tkc 202605.tkc 202606.tkc 202607.tkc  ticks.dat
```
This is the **standard MetaTrader terminal history-store layout** — `bases\<server>\history\<symbol>\<year>.hcc`
and `bases\<server>\ticks\<symbol>\<YYYYMM>.tkc` — documented in MetaTrader's own "Files and
Folders" help page, *not* a special/separate "Strategy Tester only" cache format. One
`.hcc` file per **year** (not month), so `2026.hcc` alone contains whatever M1 range the
terminal pulled for all of 2026, which per the task context includes Jan–Mar. The monthly
tick files (`202601.tkc`…`202603.tkc`) independently corroborate that Jan/Feb/Mar 2026
data physically exists in this store, not just May onward.

This matters because it directly contradicts a fear that the tester's cache is a
throwaway/inaccessible black box: it is written into the **same file layout used by any
ordinary MT5 terminal**, and per MetaTrader's own documentation this store is exactly
what `copy_rates_from`/`copy_rates_range` read from when a terminal is initialized against
that data folder.

## Path A (recommended): Point the MT5 Python API at the Tester's own terminal

**Mechanism.** `D:\FOREX\MT5_Tester` is a full, separate MetaTrader terminal installation
(it has its own `terminal64.exe`, `MQL5`, `Bases`, `Config`, `Profiles`) — it is not just a
tester-agent sandbox bolted onto `MT5_Portable`. The MetaTrader5 Python package's
`initialize(path=...)` accepts the path to *any* terminal executable and attaches to *that*
terminal's data folder. Once attached, `copy_rates_range("XAUUSD", mt5.TIMEFRAME_M1,
datetime(2026,1,1), datetime(2026,3,26))` asks the **attached terminal** for bars in that
range; per MQL5 docs, if the terminal already has the data locally (built from its own
`Bases\<server>\history\<symbol>\*.hcc`) it is returned immediately — no server round-trip
is required. Since this terminal's `Bases\Capitaria-All\history\XAUUSD\2026.hcc` and the
`ticks\XAUUSD\2026{01,02,03}.tkc` files already exist from when the Strategy Tester
downloaded Jan–May 2026 to prepare for the backtest, the request should resolve from the
local store even if Capitaria's *live* server no longer serves that range (which is exactly
the situation the M1 lake gap already demonstrates for the other, `MT5_Portable`, terminal).

**Steps:**
1. Do NOT reuse the already-running `MT5_Portable` terminal (that's the one whose
   `copy_rates_from` paging already proved it can't reach before 2026-03-25 live).
2. Launch/attach specifically to `D:\FOREX\MT5_Tester\terminal64.exe` — either open it
   interactively once (so it's a live logged-in session against `Capitaria-All`) or call
   `mt5.initialize(path=r"D:\FOREX\MT5_Tester\terminal64.exe")` from Python directly.
3. Call `mt5.copy_rates_range("XAUUSD", mt5.TIMEFRAME_M1, datetime(2026,1,1,tzinfo=timezone.utc), datetime(2026,3,26,tzinfo=timezone.utc))`.
   Also try `TIMEFRAME_M5`/`M15` (M2 is not an MT5 native timeframe — MT5 only has
   M1,M2,M3,M4,M5,M6,M10,M12,M15,M20,M30 — actually M2 *is* native in MT5's timeframe enum,
   so it's requestable directly if needed, no synthetic resampling required).
4. If the call returns `None`/empty, it means the terminal doesn't recognize the range as
   "ready" and is trying to negotiate a fresh download from the (currently
   history-limited) live server — see Risk below. If it returns bars, dump straight to CSV
   (`time,open,high,low,close,volume`, ISO-8601 UTC) and feed into the existing
   `sentinel_engine.lake.ingest_mt5.ingest_mt5_csv(csv, "XAUUSD", 1, lake_root)` (and
   again with `5`, `15` for the other timeframes) — this is literally the function this
   codebase already has for this exact CSV shape.
5. Cross-cache trick if step 3 stalls: open History Center (F2) *in that same MT5_Tester
   terminal*, select XAUUSD/M1, and use "Export" — Export reads from the same local store
   the API reads from and writes CSV/HTM/PRN directly, sidestepping any Python-API
   negotiation quirks. This produces a CSV nearly ingestible as-is (modulo header/column
   renaming to match `time,open,high,low,close,volume`).

**Confidence: Medium-High.** The physical evidence (files exist, right layout, right
year/months) is strong. The uncertainty is procedural, not data-existence: does
`copy_rates_range` requesting a range for which the *local* cache has data, but which the
*live* server would refuse if asked fresh, actually short-circuit to local data, or does it
always re-validate/re-request from the server first and fail/timeout if the server has
aged the range out? MQL5's own docs are explicit that "if the terminal does not have data
locally, downloading is initiated" — the converse implication (if it DOES have it locally,
no download is initiated) is stated but not exhaustively proven for the tester-vs-terminal
history split; the MQL5 forum thread on this point (mql5.com/en/forum/356530) confirms the
tester keeps its own synchronized cache but does not explicitly confirm cross-readability
from the plain terminal API. Treat this as the one open unknown; step 4 in the steps above
is designed to detect it early and step 5 is the fallback if it doesn't short-circuit.

**Risks:**
- If `MT5_Tester` requires an active login/connection to Capitaria to even open the
  symbol's chart (some brokers gate History Center access behind a live session), and the
  demo/tester login has since expired or the account was tied to a specific tester run,
  reconnecting may itself trigger a fresh (limited) history negotiation that overwrites or
  ignores the cached `2026.hcc` — back up `D:\FOREX\MT5_Tester\Bases\Capitaria-All\history\XAUUSD\2026.hcc`
  and the `ticks\XAUUSD\2026{01,02,03}.tkc` files before touching that terminal, so a
  failed attempt can't destroy the one copy of the data we're trying to extract.
- `.hcc`/`.tkc` are undocumented proprietary MetaQuotes formats (confirmed — MetaQuotes has
  not published a spec); this path deliberately avoids parsing them directly and instead
  goes through the terminal + official API/Export, which is the only supported read path.
- If M1 for Jan–Mar came from the tester's **synthetic tick generation** (MT5 testers can
  generate ticks from M1 "OHLC" mode when real ticks are unavailable) rather than real
  broker M1, the bars could be slightly reconstructed rather than the broker's authentic
  M1. Given the task's own stated purpose (chart visualization of imported trades, not the
  parity-gated scorer), this is an acceptable risk — but worth a sanity check comparing a
  known-good stretch (e.g. late March, where we have both the live-fed lake data and this
  cache) for a spot-check that the reconstructed vs. live bars agree closely.

## Path B: Force History Center / chart scroll on the live Capitaria connection

Standard MT5 mechanism: Tools→Options→Charts, set "Max bars in chart"/"Max bars in
history" to Unlimited or a very large number, then scroll a XAUUSD M1 chart back to
January or open History Center (F2) and request the range — this is what actually
"asks the server again" rather than relying on any local cache. **This is very likely to
fail for this specific gap**, because the task context states this was *already tried*
in effect (`mt5_dump_history.py` paging backward via `copy_rates_from` already hit a wall
at 2026-03-25) — the client-side cap (`Max bars`) is not the blocker here since the script
was explicitly paging further back and still got refused; that points to the **server's
own retention window**, not a client display limit. Worth ~15 minutes to try (cheap,
doesn't preclude Path A), but treat as a low-confidence fallback, not the primary plan.
**Confidence: Low** given the existing negative evidence.

## Path C: Capitaria server-side retention — confirmed unknown, likely short for M1

No public documentation was found (broker site, MQL5 community, forums) stating
Capitaria's specific M1 history retention window for XAUUSD or any symbol. This is
consistent with most retail MT5 brokers: **M1 history depth is a server-side policy, not
protocol-mandated**, and brokers commonly cap deep M1 retention (weeks to a few months is
common for smaller/newer servers) while retaining H1/D1 far longer, since M1 storage is
the most space/bandwidth-costly tier. Capitaria's public materials (capitaria.com,
mt5-ktgroup web terminal) don't publish a retention policy, and third-party broker-review
sites (WikiFX, ForexPeaceArmy, etc.) discuss spreads/regulatory concerns, not history
depth. **This can only be confirmed by asking Capitaria support directly** (fastest
outside-path: live chat / support ticket asking specifically "what is your MT5 M1 history
retention for XAUUSD"). Not pursued further here since Path A's local cache makes it
likely moot for this specific date range — but flagged as the fallback question if Path A
turns out to have re-requested from the (now history-limited) server rather than serving
from `2026.hcc`.

## Path D: Dukascopy XAUUSD M1/tick (third-party, standard-symbol feed)

**Mechanism.** Dukascopy Bank SA publishes free historical tick data for XAUUSD ("Spot
gold") going back 15+ years, exportable via their own Historical Data Export tool
(dukascopy.com/swiss/english/marketwatch/historical/) in CSV, and via open-source
downloaders (`dukascopy-node`, `duka` Python CLI, `theorycraft-trading/dukascopy`) at tick,
s1, m1, m5, m15, m30, h1+ aggregations. This is the standard fallback used broadly in the
retail-quant community precisely because most brokers don't offer deep M1 retention.

**Why it's admissible here per the task's own rule**: the project's hard-rule bans
Dukascopy only for *broker-specific-contract* symbols (where the broker's own instrument
differs materially from a generic feed — different contract spec, different session
times, synthetic index, etc.). XAUUSD is a standard, globally-quoted spot-gold price;
Dukascopy's own XAUUSD is itself a well-known reference feed used across the industry for
this exact symbol. And the stated purpose here is chart visualization backing an imported
trade record — not the parity-gated scorer that the hard-rule is protecting. This makes
Dukascopy a legitimate *secondary* option if Path A's cache-read doesn't pan out.

**Steps:**
1. Use `dukascopy-node` (or `duka`) to pull XAUUSD, `m1` (and `m5`/`m15`), 2026-01-01 →
   2026-03-26, UTC.
2. Reformat the export to the lake's expected columns exactly:
   `time,open,high,low,close,volume` with `time` ISO-8601 UTC (Dukascopy exports are UTC
   already, but confirm column order/names — likely need a rename/reorder pass, no
   timezone conversion needed).
3. `sentinel_engine.research.ingest_mt5_deals`... no — use
   `sentinel_engine.lake.ingest_mt5.ingest_mt5_csv(csv_path, "XAUUSD", 1, lake_root)` (and
   `5`, `15`) exactly as Path A's output would be ingested; the ingester doesn't care which
   upstream produced the CSV as long as the five columns are named/typed correctly.

**Confidence: High** that the *data itself* is obtainable (Dukascopy's XAUUSD history for
this period unquestionably exists and is free). **Medium** on fidelity for this specific
use: Dukascopy is its own liquidity venue's composite price, not Capitaria's own quote
stream — bid/ask spread, occasional gap timing, and exact wick highs/lows can differ from
what Capitaria showed at the same instant, especially around low-liquidity hours or
weekend-open gaps. Acceptable for visual chart context around already-known trade
prices/times (which come from the `.htm` import, not from these bars) — NOT acceptable
if any code path derives price-dependent logic (fills, SL/TP hits) FROM these bars rather
than from the imported MT5 deal record.

**Risks:**
- Timezone/session-boundary mismatches: Dukascopy's day boundary and Capitaria's server
  time may not align exactly, so daily/session aggregates could shift by an hour; M1/M5/M15
  raw bars are less affected than daily rollups.
- Spread differences mean any OHLC that's silently "ask" vs "bid" convention could differ
  from Capitaria's displayed candle by a few points during volatile moments — irrelevant
  for the stated visualization purpose, worth flagging in the UI as "reference feed" if
  ever shown side-by-side with genuine Capitaria bars.

## Recommended path and rationale

**Do Path A first.** The Jan–Mar 2026 XAUUSD data is not actually missing from this
machine — it's sitting in `D:\FOREX\MT5_Tester\Bases\Capitaria-All\history\XAUUSD\2026.hcc`
and `ticks\XAUUSD\202601-03.tkc` in the same layout any MT5 terminal reads from. The
correct framing isn't "the deep history is unavailable," it's "the live-connected
`MT5_Portable` terminal's server no longer serves it, but a still-cached second terminal
instance might." This is a same-day, zero-new-dependency check (attach Python API or open
History Center against `MT5_Tester`, not `MT5_Portable`) before reaching for any
third-party feed. If — and only if — that terminal's local cache turns out to have been
invalidated/pruned or the API insists on re-negotiating with the live server and fails,
fall back immediately to Path D (Dukascopy), which is unambiguously available, free, fits
the existing `ingest_mt5_csv` pipeline unmodified, and is fit-for-purpose given the
explicitly stated visualization-only (non-parity-gated) use case.

## Sources

- [MetaTrader 5: History in MT5](http://metatrader5.blogspot.com/2009/10/history-in-metatrader-5.html)
- [Files and Folders — For Advanced Users — MetaTrader 5 Help](https://www.metatrader5.com/en/terminal/help/start_advanced/structure)
- [MQL5 Docs: Timeseries and Indicators Access](https://www.mql5.com/en/docs/series/timeseries_access)
- [.hcc and .hc files — MQL5 forum](https://www.mql5.com/en/forum/74117)
- [History data: history/cache/ticks folder differences — MQL5 forum](https://www.mql5.com/en/forum/340054)
- [copy_rates_range — MQL5 Python Integration docs](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py)
- [copy_rates_from — MQL5 Python Integration docs](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py)
- [CopyRates — MQL5 Timeseries docs](https://www.mql5.com/en/docs/series/copyrates)
- [History Data Structure (MqlRates) — MQL5 docs](https://www.mql5.com/en/docs/constants/structures/mqlrates)
- [How the Tester Downloads Historical Data — MetaTrader 5 Help](https://www.metatrader5.com/en/terminal/help/algotrading/test_preparation)
- [Strategy tester cache — MQL5 forum](https://www.mql5.com/en/forum/356530)
- [Platform Settings ("Max bars in chart/history") — MetaTrader 5 Help](https://www.metatrader5.com/en/terminal/help/startworking/settings)
- [Limit max number of bars in history — MQL5 forum](https://www.mql5.com/en/forum/465918)
- [How Do You Access and Use Historical Data in MetaTrader 5 Correctly? — Headway](https://hw.online/faq/metatrader-5-history-data/)
- [How to download history data in MT5 — Forex Factory](https://www.forexfactory.com/thread/435087-how-to-download-history-data-in-mt5)
- [MT4/MT5: Export historical data — Myforex guide](https://myforex.com/en/mt5guide/export-historicaldata.html)
- [Capitaria — MT5 Web](https://www.capitaria.com/mt5-ktgroup)
- [CAPITARIA Review — WikiFX](https://www.wikifx.com/en/dealer/6451315853.html)
- [Is CAPITARIA Broker Safe — Wikibit](https://forex.wikibit.com/en/brokers/safe/capitaria-6451315853.html)
- [Dukascopy XAUUSD historical tick data — dukascopy-node.app](https://www.dukascopy-node.app/instrument/xauusd)
- [Forex Historical Data Export — Dukascopy Bank SA](https://www.dukascopy.com/swiss/english/marketwatch/historical/)
- [dukascopy-node — GitHub (theorycraft-trading)](https://github.com/theorycraft-trading/dukascopy)
- [duka — Dukascopy data downloader](https://giuse88.github.io/duka/)
- [Free historical data from Dukascopy — Blue Capital Trading](https://www.bluecapitaltrading.com/products/free-historical-data/)
- [Top 12 Sources to Download Forex Historical Data](https://newyorkcityservers.com/blog/top-12-sources-to-download-forex-historical-data-free-paid)

## Local evidence referenced (not sources, but facts checked this session)

- `D:\FOREX\MT5_Tester\Bases\Capitaria-All\history\XAUUSD\` — `2014.hcc` … `2026.hcc`, `cache`
- `D:\FOREX\MT5_Tester\Bases\Capitaria-All\ticks\XAUUSD\` — `202601.tkc` … `202607.tkc`, `ticks.dat`
- `D:\FOREX\MT5_Tester\terminal64.exe` — a full separate terminal install (own `Bases`,`Config`,`MQL5`,`Profiles`)
- `D:\FOREX\sentinel_engine\lake\ingest_mt5.py` — `read_mt5_csv`/`ingest_mt5_csv`: requires first column named `time` plus `BAR_COLUMNS` (open/high/low/close/volume), parsed via `pd.to_datetime(..., utc=True)`
