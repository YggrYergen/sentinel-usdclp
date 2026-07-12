# P2 ‖ P3 Parallel Execution — File-Ownership Contract

> Hard rule (user directive): the two parallel routes must NEVER write the same file.
> Every agent on either route receives this contract verbatim and MUST obey it.
> Orchestrator (Opus) owns all commits and all shared-file edits. Agents leave the
> working tree dirty and REPORT; they do NOT run git.

## ROUTE P2 — Data lake + point-in-time replayer  (Sonnet; 2-strikes gate)
EXCLUSIVE WRITE OWNERSHIP (create/modify only these):
- `sentinel_engine/lake/**`            → ingest_dukascopy.py, ingest_mt5.py, manifest.py, __init__.py
- `sentinel_engine/trades/**`          → ingest_xtb.py, ingest_mt5_trades.py, schema.py, __init__.py
- `sentinel_engine/feed_historical.py` → HistoricalFeed
- `sentinel_engine/timeline.py`        → TimelineAligner
- `tests/lake/**`, `tests/trades/**`   → its tests + synthetic fixtures ONLY
May READ (never write): the SHARED-READONLY set below + `tests/golden/fixtures/csv/**` as a price-data source.

## ROUTE P3 — FastAPI service + thin frontend  (Sonnet)
EXCLUSIVE WRITE OWNERSHIP (create/modify only these):
- `sentinel_engine/service/**`         → app.py, stream.py, __init__.py  (DO NOT create chat.py — reserved for P5)
- `web/**`                             → index.html, app.js, style.css, vendored uPlot (NO CDN)
- `tests/service/**`                   → its tests ONLY
May READ (never write): the SHARED-READONLY set below.

## SHARED — READ-ONLY for BOTH routes (modifying = contract violation)
- Scoring core, FROZEN by the parity gate: `sentinel_engine/engine.py`, `config.py`, `macro.py`,
  `technical.py`, `feed.py`, `ai_context.py`, `sentinel_engine/instruments/**`
- All of `sentinel/**`
- `tests/golden/**`, `tests/test_*.py` at repo root, existing fixtures

## ROUTE THROUGH ORCHESTRATOR ONLY (neither agent edits; report the need, I serialize it)
- `sentinel_engine/__init__.py` (shared package init) — pre-created empty per subpackage by orchestrator
- `requirements.txt` / any dependency manifest
- `.gitignore` (P2's generated data dirs, e.g. a lake output path, get ignored here)
- `tests/conftest.py` (shared) — each route uses its OWN `tests/<route>/conftest.py` instead
- tracker / ledger / pinned

## HARD DON'Ts (both routes)
- Real broker accounts are READ-ONLY — MT5/price ingesters READ only; NEVER place orders.
- Windows 10 AND 11: pathlib only, explicit utf-8, no OS-version APIs, no WSL assumptions.
- Do NOT run git (no commit/add/tag/reset/revert/worktree). Leave the tree dirty; report.
- Do NOT touch the sibling worktree `D:/FOREX_baseline_2026-06-11`.
- Do NOT fabricate real market data. If a task needs a real external sample you lack (XTB export,
  Dukascopy download), BUILD the adapter + a format-accurate SYNTHETIC fixture, make the test pass
  against the synthetic fixture, and FLAG the task "NEEDS REAL-SAMPLE VALIDATION" in your report.
- Do NOT modify the scoring core or any file the other route owns. If you think you need to, STOP and report.

## Intra-route write-collision rule (within P3's parallel stage)
- The package `__init__.py` files are pre-created (empty) by the orchestrator BEFORE fan-out, so no
  two parallel agents race to create them. Each parallel agent writes only its own module file(s).
