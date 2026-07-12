# SENTINEL Revamp — Implementation Workflow & Governance

> Date: 2026-07-07 | Status: approved | Owner: user (YggrYergen)
> Companion design (technical): `FABLE5_RESPONSE_SENTINEL_REVAMP.md`
> Briefing: `BRIEFING_SENTINEL_REVAMP.md`
> This document governs HOW the revamp is implemented (model routing, agent
> protocol, escalation, tracker rules, OS requirements). The WHAT lives in the
> phased plan produced by writing-plans and in the brain project ledger.

## 0. Purpose

Fable 5 delivered the technical design. This document defines the **cost-minimized
dynamic agentic workflow** that turns that design into shipped code with the
smallest possible spend of the expensive model (Opus 4.8), while keeping
direction locked so implementer agents never have to analyze — only implement.

## 1. Session boundary (critical)

- **The planning session runs in WSL and writes NO source code.** Its only
  outputs are: this spec, the P0–P7 plan, the brain project ledger
  (`plan.md` + `tracker.md`), and updated `pinned.md` + active thread.
- **Implementation happens on the Windows dev machine, in PowerShell, in a
  fresh `claude` session.** SessionStart reseeds context from brain
  (`pinned.md` + `INDEX.md` + active thread handoff). Implementation begins at P0.
- Rationale: reset the context window before the expensive implementation work;
  keep the WSL box as the plan-authoring surface only.

## 2. Phase map (from Fable's §6)

| Phase | Deliverable | Model |
|---|---|---|
| P0 | Golden-master parity harness; fix 2 defects (`CorrelationEngine` import guard, replay `normalize_macd=True`); regenerate AI-context numbers from config; Streamlit stopgap (bg thread + `st.fragment`); **start tick+snapshot loggers now** | Sonnet 5 (Haiku for trivial subtasks) |
| **P1** | `sentinel_engine/` headless core: `InstrumentConfig` (3 YAMLs from `config.py`), parameterized `MacroScorer`, `Feed` protocol, `Engine.step()→Snapshot`, snapshot schema + AI-context renderer; parity green on all 3 instruments; delete inline macro copy in `instrument_panel` | **Opus 4.8** |
| P2 | Data lake (Dukascopy + MT5, Parquet + manifests), `HistoricalFeed(as_of)`, `TimelineAligner`, trade ingesters (XTB/MT5 adapters, schema-validated) | Sonnet 5 **+ 2-strikes escalation gate** |
| P3 | FastAPI + uvicorn service (`/snapshot`, `WS /stream`, `/history`, `/chat`, `/config`); single static HTML/CSS/vanilla-JS page + WS client (uPlot charts); golden-master UI parity | Sonnet 5 (**Fable one-shot candidate — see §5**) |
| **P4** | Optimization + validation engine: Optuna TPE + staged block-wise grids (3–8 dims/fit); triple-barrier labels + reference-policy PnL; anchored walk-forward + 1-day embargo + purged labels; median-fold selection with ≥70%-fold dominance; plateau (±10%) + regime-balance checks; single-touch holdout; deflated Sharpe; SQLite+Parquet registry | **Opus 4.8** (+ Fable design pass — see §5) |
| P5 | Re-enable AI assistant; context built from snapshot + MT5 positions (kills prompt drift) | Sonnet 5 (Haiku trivial) |
| P6 | `RegimeLabeler` + per-day/per-symbol regime table; global-first / regime-delta-second per-asset tuning | Sonnet 5 |
| P7 | Monthly retune runbook + report | Sonnet 5 |

## 3. Model routing policy

- **Opus 4.8 is spent on exactly two phases: P1 and P4.** These are the phases
  where a cheap model's errors are *silent* and *inherited*: P1 is the
  architectural keystone every axis consumes; P4 is subtle validation
  statistics where a bug yields overfit garbage that looks correct.
- **Sonnet 5 is the default implementer** for all mechanical phases (P0, P2, P3,
  P5, P6, P7).
- **Haiku 4.5** only for trivially mechanical subtasks (config edits, file moves,
  pure boilerplate) explicitly tagged `[haiku-ok]` in the tracker.
- **Sonnet-5-high** is used only inside an Opus escalation (§4), sparingly.

## 4. The 2-strikes escalation rule (global; formalized in P2)

- A **strike** = an implementer task fails its acceptance check twice in a row on
  the same task. "Fails" = parity test red, unexpected runtime behavior, or a
  deviation from the closed spec.
- **On the 2nd strike:** STOP → run `/brain update` recording the failure
  evidence (inputs, expected vs actual, last diff) → hand the task to an **Opus
  orchestrator**. The Opus orchestrator implements directly when the remaining
  work is small; it dispatches **Sonnet-5-high** sub-agents sparingly only when
  length demands it.
- Purpose: cap cheap-model thrash on hard tasks; guarantee a hard task never
  loops more than twice before a capable model takes over.
- P2 (replayer / look-ahead-sensitive) is the designated proving ground for this
  rule because leakage bugs are the most likely to trip it.

## 5. Fable 5 one-shot — reserved and gated

- **Budget: exactly one Fable 5 one-shot** across the whole revamp.
- **Provisional target: a P4 optimizer/validation design pass** that Opus then
  implements.
- **Decision gate (mandatory) immediately before P4 starts:** re-evaluate with
  fresh evidence whether Fable is still the highest-benefit use of the one-shot,
  or whether it should be redirected (candidates: holistic P3 frontend build; a
  cross-phase design review; a hard sub-problem surfaced during P1–P3). Record
  the decision + rationale in the tracker. The one-shot is **never auto-spent.**

## 6. Brain protocol for agents

- **Tasks are closed.** Implementer agents implement; they do not analyze,
  propose, or conjecture. Each agent: reads its task from `tracker.md`,
  implements exactly, runs the stated acceptance check, leaves a crumb.
- **The orchestrator writes handoffs at phase boundaries** (one `/brain handoff`
  per phase exit), not the sub-agents.
- **`tracker.md` is the single source of task truth** and is INTOCABLE (brain
  budget-guard denies >20% shrink) while the project is `active`.
- **Every phase closes** with `brain close-impl --analyze` → `--apply` only when
  its exit gate is green.

## 7. Windows 10 + Windows 11 (hard requirement, cross-cutting)

- **Every phase's acceptance includes: "runs on Windows 10 AND Windows 11."**
- Rules enforced in every task: `pathlib` only (no hardcoded separators); no
  OS-version-specific APIs; reuse the existing embedded-Python launcher path;
  no WSL-only assumptions; UTF-8 explicit on all file I/O; no reliance on a
  system Python. If `pywebview`/WebView2 is ever introduced, verify WebView2
  presence on both OSes first.
- This constraint lives in `pinned.md` so it is injected into every
  implementation session.

## 8. Tracker shape ("brief but complete, respected")

One dedicated brain ledger (`brains/D--FOREX/project/`). Per phase:
`goal · closed task list (exact files / signatures / acceptance check) ·
model assignment · dependency · exit gate`. Brief enough to keep interaction
cost low; complete enough that an implementer never reasons about *what* — only
executes *how*.

## 9. Definition of done for THIS (planning) session

1. This spec written + committed.
2. Full P0–P7 plan authored (writing-plans) with closed tasks.
3. Brain project ledger initialized; plan/tracker populated + protected.
4. `pinned.md` updated (Win10+11 rule, no-code-in-WSL, model routing, 2-strikes).
5. Active thread handoff refreshed for a **fresh PowerShell/Windows session**.
6. Windows handoff message delivered to the user.
