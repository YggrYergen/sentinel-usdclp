# Research: Presenting Financial Time-Series Data to Claude for Trading Analysis

Status: research spec (not an implementation plan)
Audience: Sentinel chat-assistant design (position dossier + strategy review dossier)
Target models: Claude Opus 4.8 (`claude-opus-4-8`), secondary Claude Sonnet 5 (`claude-sonnet-5`)
Date: 2026-07-12

---

## 1. Executive Summary

**The team's assumption — "compact CSV-style tables + aggregated statistics outperform raw JSON
arrays for numeric series" — is DIRECTIONALLY CORRECT but the literature complicates it in two
important ways.** Full picture, cross-checked against peer-reviewed papers, official Anthropic
docs (fetched directly), and multi-source practitioner benchmarks:

1. **"CSV beats JSON" is true for token cost, essentially always, and true for accuracy on
   flat/uniform data in most — but not all — practitioner benchmarks found.** One rigorous
   independent benchmark (single-model, GPT-4.1-nano) found **CSV was actually the *worst*
   format tested for comprehension accuracy (44.3%)**, behind Markdown-KV (60.7%), XML (56.0%),
   YAML (54.7%), and even plain JSON (52.3%) — while remaining by far the cheapest in tokens
   (19,524 vs 52,104 for Markdown-KV on the same data). A separate, more model-diverse benchmark
   (TOON project, 4 models including **Claude Haiku 4.5**) found that on genuinely flat/uniform
   tabular data specifically, CSV-like formats remain **token-competitive**, and accuracy
   differences across formats are much smaller than on nested/mixed data. **Verdict: token-cost
   claim is confirmed strongly; the accuracy claim is confirmed only weakly and is not
   universal — it should be validated empirically for this app via the mini-eval (§9), not
   assumed.** This is the single most important correction to the team's assumption.
2. **"Aggregated statistics outperform raw arrays" is right for strategy review, wrong as a
   blanket rule for single-position analysis, and has a sharper evidentiary basis than initially
   assumed: LLMs are specifically weak at aggregation/filtering computed from raw rows.** The
   TOON benchmark found field-*retrieval* accuracy of 99.6% but aggregation accuracy of only
   ~61.9% and filtering accuracy of only ~56.8% — a large, format-independent gap. This means
   asking Claude to compute "average MAE across these 80 trades" from a raw table is
   *structurally* unreliable regardless of format choice — the fix is not a better format, it's
   **not asking the model to aggregate at all**: compute stats server-side, hand them over as
   ground truth, and reserve the model's job for interpretation/citation of specifics. A
   practitioner trading system found in this research (QuantAgent, arXiv:2509.09995) makes
   exactly this architectural choice — it does not feed raw OHLC to its LLM agents at all;
   indicators/signals are pre-computed and only derived values reach the model.
3. **Anthropic's own documentation gives a quantified, first-party answer to the single biggest
   structural question (RQ6): put data first, question last — "up to 30%" quality improvement
   in Anthropic's own tests** — and prescribes an exact XML pattern
   (`<document><source>...</source><document_content>...</document_content></document>`) for
   wrapping heterogeneous data sections. This is the strongest, most directly load-bearing
   evidence in this whole report because it is first-party, current (fetched 2026-07-12), and
   exactly on-topic.
4. **Claude's number tokenization is empirically NOT like GPT's**, which undercuts naively
   porting GPT/LLaMA-oriented advice (comma-grouping, digit-spacing) from the forecasting
   literature. Independent tokenizer analysis found Claude groups digit sequences by
   semantic/frequency patterns learned from training data (e.g. `999999` collapses to one
   token; `12` and `78` have dedicated tokens but `23`/`34` don't) rather than a fixed rule like
   GPT's 3-digit-from-the-right chunking or LLaMA's pure single-digit split. **No controlled
   study of Claude + numeric-formatting-choice + downstream accuracy exists — this is a genuine
   evidence gap**, flagged explicitly in §7. The one number-formatting recommendation that
   survives regardless of tokenizer quirks: **fixed, consistent decimal precision per column**
   (justified by the general finding that consistent formatting supports place-value pattern
   matching, not by a Claude-specific ablation).
5. **Tool use vs. context-stuffing has explicit, first-party Anthropic guidance that maps
   cleanly onto this app's two use cases**: "start simple" (single-call, in-context data is
   "usually enough") for bounded data, moving to a **hybrid** — summary in context up front,
   full history queryable via a narrowly-scoped tool — once data no longer fits comfortably or
   the task is exploratory/multi-turn (Anthropic engineering blog, "Effective context
   engineering," Sept 2025). Anthropic's own default tool-response cap in Claude Code is
   **25,000 tokens** — a concrete number worth adopting as this app's default `get_trade_bars`
   response ceiling too.

**Net verdict on the assumption as literally written:** confirmed for the strategy-review
surface and confirmed on token cost universally; the accuracy half of the claim is **not
universally supported by the evidence** and should be treated as a hypothesis to validate via
the mini-eval, not a settled fact — this is a genuine, load-bearing revision to what the team
assumed going in.

---

## 2. Findings Per Research Question

### RQ1 — Serialization format: CSV vs markdown table vs JSON vs aligned columns vs prose

**Tokenization foundations (LLMTime).** Gruver et al., *"Large Language Models Are Zero-Shot
Time Series Forecasters"* (NeurIPS 2023, peer-reviewed,
[arXiv:2310.07820](https://arxiv.org/abs/2310.07820)) is the foundational, controlled-ablation
paper on serializing numeric time series for LLM in-context consumption. Exact scheme: encode
digits space-separated within a number, commas between timesteps, drop the decimal point
entirely in favor of a fixed, tuned digit precision — e.g. `0.123, 1.23` becomes
`"1 2 , 1 2 3"`. **Critical finding from their own ablation (Fig. 2, Australian Wine dataset):
this only helps models whose tokenizer does NOT already split digits individually.** For GPT-3
(which chunks digits inconsistently), spacing helps substantially. For LLaMA-2 (which already
tokenizes digits one-at-a-time), adding spaces *hurts* — the extra space tokens are pure
overhead with no informational benefit. **This is the load-bearing caveat for our purposes**:
the "right" numeric serialization is a function of the target model's specific tokenizer
behavior, not a universal rule — see the Claude-tokenizer finding below, which shows Claude
doesn't cleanly match either the GPT or the LLaMA pattern.

**Number tokenization in GPT vs Claude.** "Tokenization counts: the impact of tokenization on
arithmetic in frontier LLMs" (peer-reviewed/arXiv,
[arXiv:2402.14903](https://arxiv.org/abs/2402.14903)) found that GPT-3.5/4's tokenizer
(`cl100k_base`) chunks numbers into groups of 3 digits **left-to-right**, which misaligns with
how arithmetic is actually computed (right-to-left, from the ones place); **comma-separating
numbers as thousands-groups (e.g. "42,235,630") forces right-to-left chunking and measurably
improves arithmetic accuracy** on GPT-family models. Independent empirical tokenizer analysis
(practitioner source, [artfish.ai](https://www.artfish.ai/p/how-would-you-tokenize-or-break-down),
using a tokenizer-comparison tool across GPT-4, Llama-3, Claude, Mixtral, Gemma) found **Claude
does not follow either the GPT 3-digit-chunking rule or the LLaMA single-digit rule** — Claude's
digit grouping appears semantic/frequency-driven from training data (repeating `999999` collapses
to a single token; `12` and `78` have dedicated tokens while adjacent pairs like `23`/`34`/`45`
do not; no tokenizer tested, including Claude's, treats `3.14159` as a coherent single unit
despite its ubiquity). **No controlled study of Claude + comma-grouping/digit-spacing +
downstream numeric-task accuracy was found** — treat any specific digit-formatting prescription
for Claude as unvalidated (§7, open question).

Foundational grounding for *why* place-value alignment matters at all: Nogueira et al.,
"Investigating the Limitations of Transformers with Simple Arithmetic Tasks"
([arXiv:2102.13019](https://ar5iv.labs.arxiv.org/html/2102.13019), well-cited arXiv) showed in a
fine-tuning setting that explicit per-digit positional markers vastly outperform both sub-word
and plain character-split encodings for arithmetic (60-digit vs 5-digit reliable addition). This
is a fine-tuning result, not a prompting result, but it explains the *mechanism* the comma-
grouping trick above exploits at the prompting level.

**Tabular format benchmarks (practitioner, cross-source, weight below peer-reviewed).**

*Benchmark 1* — [improvingagents.com, "Which Table Format Do LLMs Understand Best? (11
Formats)"](https://www.improvingagents.com/blog/best-input-data-format-for-llms/), single model
(GPT-4.1-nano), one dataset:

| Format | Accuracy | Tokens |
|---|---|---|
| Markdown-KV | 60.7% | 52,104 |
| XML | 56.0% | 76,114 |
| INI | 55.7% | 48,100 |
| YAML | 54.7% | 55,395 |
| HTML | 53.6% | 75,204 |
| JSON | 52.3% | 66,396 |
| Markdown-Table | 51.9% | 25,140 |
| Natural-Language | 49.6% | 43,411 |
| JSONL | 45.0% | 54,407 |
| **CSV** | **44.3%** | **19,524** |
| Pipe-Delimited | 41.1% | 43,098 |

**CSV was the second-worst format tested for comprehension accuracy** despite being cheapest by
token count — the direct, uncomfortable counter-evidence to the team's assumption's accuracy
half. Markdown-Table is the best accuracy/cost compromise in this specific benchmark (52% at
less than half Markdown-KV's tokens).

*Benchmark 2* — [TOON format benchmarks](https://toonformat.dev/guide/benchmarks) /
[improvingagents.com TOON writeup](https://www.improvingagents.com/blog/toon-benchmarks/),
**4 real models including Claude Haiku 4.5** (more cross-model generalizability than benchmark
1): overall TOON (a purpose-built LLM-context notation) beat JSON 76.4% vs 75.0% at 40% fewer
tokens on **mixed/nested** data — but **on genuinely flat, uniform-schema tabular data
specifically (the OHLCV case), CSV was more token-efficient than TOON** (63,997 vs 67,778
tokens) and format-accuracy differences shrank substantially. Claude Haiku 4.5 showed the
strongest same-family preference for TOON among the 4 models tested (59.8% accuracy),
suggesting some Claude-family sensitivity to format exists, though this doesn't isolate CSV
specifically. **Most important cross-cutting finding from this benchmark for this application**:
task-type accuracy breakdown was field retrieval 99.6%, structure awareness 89.0%, structural
validation 70.0%, **filtering 56.8%, aggregation 61.9%** — i.e. *regardless of format*, models
are near-perfect at looking up a specific value and much weaker at computing over many rows.
This is the strongest evidence in this whole research pass for RQ5's "don't ask the model to
aggregate" conclusion.

*Benchmark 3 (token-cost only, methodologically transparent about that limit)* —
[jangwook.net, "Stop Feeding Raw JSON to Your LLM"](https://jangwook.net/en/blog/en/llm-token-cost-data-format-experiment/),
`tiktoken`-measured, 50 flat records, explicitly states it measures tokens only, not accuracy:
TSV −62% tokens vs pretty JSON, CSV −60%, Markdown table −54%, compact JSON −37.5%, YAML −23.5%,
XML +16% (worst). Confirms flat/tabular formats' token advantage is large and consistent; explicit
recommendation to strip pretty-printing/indentation before sending JSON to an LLM if JSON must be
used, and to re-verify accuracy empirically whenever changing format since token savings and
accuracy do not necessarily move together — directly matches this report's own emphasis on the
mini-eval (§9).

**Reconciling the accuracy disagreement between benchmarks 1 and 2**: benchmark 1's CSV-is-worst
result and benchmark 2's CSV-is-competitive-on-flat-data result are not strictly contradictory —
benchmark 1 tested one model on presumably more heterogeneous data, benchmark 2 specifically
isolated "flat, uniform-schema" data (which is what OHLCV actually is) and found the accuracy gap
narrows there. **The safest reading: CSV's accuracy risk is real and format-dependent enough
that this app should not assume CSV is safe by default — it should validate CSV specifically
against at least one accuracy-oriented alternative (Markdown table) on this app's actual OHLCV/
trade schema via the mini-eval**, rather than treating "CSV wins" as settled.

**Recommendation, revised from the initial draft**: default to **Markdown tables** (not bare
CSV) for OHLCV/indicator series and for the strategy-review per-trade summary table — the token
premium over CSV is real (~15-50% depending on benchmark) but small in absolute terms at this
app's data volumes (§RQ2 budget), and Markdown tables were never the worst performer in either
accuracy benchmark while CSV was the worst in one of the two. Reserve raw CSV/plain-aligned
columns only if the mini-eval (§9) empirically shows no accuracy cost for this app's specific
schema and questions. Compact JSON remains right for small, irregular, or nested structures
(trade metadata envelope, signal-panel snapshots) — never for large flat numeric tables, where
its token cost is worst-in-class across every benchmark found (RQ8).

*Sources: [arXiv:2310.07820 (LLMTime)](https://arxiv.org/abs/2310.07820),
[arXiv:2402.14903 (Tokenization counts)](https://arxiv.org/abs/2402.14903),
[arXiv:2102.13019 (Nogueira et al.)](https://ar5iv.labs.arxiv.org/html/2102.13019),
[artfish.ai tokenizer comparison](https://www.artfish.ai/p/how-would-you-tokenize-or-break-down),
[improvingagents.com table-format benchmark](https://www.improvingagents.com/blog/best-input-data-format-for-llms/),
[TOON benchmarks](https://toonformat.dev/guide/benchmarks),
[jangwook.net token-cost experiment](https://jangwook.net/en/blog/en/llm-token-cost-data-format-experiment/).*

### RQ2 — Token budgets, degradation, windowing

**"Lost in the middle."** Liu et al. established a U-shaped retrieval-accuracy curve across long
contexts — best at the start/end, degrading by 30%+ in the middle — replicated across multiple
models **including Claude 1.3** in the original study (per secondary summaries of the paper; the
Claude-inclusion detail matters because it means the effect is not GPT-specific). Proposed
architectural cause (via [emergentmind.com](https://www.emergentmind.com/topics/context-degradation-in-llms)
and the mitigation paper "Found in the Middle,"
[arXiv:2403.04797](https://arxiv.org/pdf/2403.04797)): RoPE's long-term decay property reduces
attention-score similarity for distant token pairs, and softmax normalization then concentrates
attention on the nearest tokens, systematically starving mid-context information. This is
architecture-level, not a training artifact specific to one model family, so it is reasonable to
expect it still applies, to some attenuated degree, in modern long-context Claude models —
Anthropic's own docs corroborate the general shape of this concern under the name **"context
rot"** (see RQ6).

**No study was found that specifically tests lost-in-the-middle on long runs of repeated-schema
numeric rows** (e.g. 500 OHLCV bars) as opposed to prose/QA retrieval — this is a genuine
evidence gap, flagged in §7. The closest indirect evidence is the TOON benchmark's task-type
breakdown (RQ1): aggregation/filtering accuracy (~57-62%) is far below field-retrieval accuracy
(99.6%) *regardless of context length in that benchmark* — suggesting the dominant failure mode
for large tabular data may be "can't reliably compute across many rows" more than "can't find a
specific row," which is a related but distinct failure mode from classic lost-in-the-middle.
Both point the same direction operationally: **don't rely on the model to scan/compute over long
row runs; keep what it must compute over short, and pre-compute the rest.**

**Practical token budgets** (INFERENCE, using this codebase's actual schema — no external
benchmark specifies a number for this exact application):

- **Position dossier (single closed trade)**: target **3,000–8,000 tokens total**. A windowed
  OHLCV table of ~40-60 bars with 6-8 numeric columns in Markdown-table form runs roughly
  20-30 tokens/row including delimiters → 800-1,800 tokens per timeframe window (a modest
  increase over the CSV estimate in light of the RQ1 revision toward Markdown). Budget 2-3
  timeframes and this lands at 2,500-4,500 tokens for raw data, leaving headroom for trade
  metadata, derived stats, and the question. This stays comfortably inside the window and well
  under Anthropic's Claude Code default tool-response ceiling of 25,000 tokens (RQ7) even before
  considering the 1M context window Opus 4.8/Sonnet 5 both provide by default.
- **Strategy review dossier (dozens-hundreds of trades)**: raw-dump does not scale — 200 trades
  × even a 10-bar window each would be 40,000+ tokens of bars alone, most of it wasted on
  unremarkable trades. Target **8,000–20,000 tokens** for the stuffed portion: O(1)-cost
  aggregate stats block (computed server-side, not by the model — RQ5), a compact one-row-per-
  trade summary table (no bars — cheap even at hundreds of rows, ~3,000-5,000 tokens at 200
  trades in Markdown form), plus **curated raw-bar excerpts for a bounded subset only**
  (worst-N, near-miss-N, trader-named — §5).
- **Confirmed by first-party Anthropic docs (RQ6)**: everything in the request — system prompt,
  every message, tool results, tool *definitions* — counts toward the context window; caching
  changes what you pay, not whether it counts against the window. This matters for a design that
  adds several tool definitions (`get_trade_bars`, `get_trade_detail`) — their schemas are a
  fixed context cost paid on every turn regardless of whether they're invoked.

**Windowing strategy**: event-centered windows (N bars before entry, M bars after exit) strictly
dominate full-session dumps — bars far from the decision point add no evidential value and dilute
attention on the ones that matter, consistent with both the lost-in-the-middle literature and
Anthropic's context-rot framing. Recommended starting default: **N=20 bars before entry, M=20
bars after exit at the entry timeframe**, plus a coarser-timeframe window of ~10-15 bars centered
on entry for multi-timeframe grounding (RQ4). These are design defaults to validate via the
mini-eval (§9), not literature-derived constants.

*Sources: Liu et al. lost-in-the-middle (via
[emergentmind.com summary](https://www.emergentmind.com/topics/context-degradation-in-llms) and
[arXiv:2403.04797](https://arxiv.org/pdf/2403.04797)); Anthropic
[context windows docs](https://platform.claude.com/docs/en/build-with-claude/context-windows.md)
(fetched 2026-07-12); TOON benchmark task breakdown (RQ1 sources); budget figures are this
report's own estimation, marked INFERENCE.*

### RQ3 — Numeric precision and formatting

- **Fixed, consistent decimal precision per column** remains the one recommendation that
  survives regardless of Claude's specific (non-standard) tokenization behavior: consistent
  significant-digit counts support place-value pattern matching in a way ragged precision does
  not, per the general mechanism established in Nogueira et al. and indirectly corroborated by
  the GPT comma-grouping result. **Action unchanged from initial assessment**: pick one decimal
  precision per instrument/column (driven by tick size) and hold it for the whole table.
- **Comma-grouping thousands separators**: the GPT-family evidence
  ([arXiv:2402.14903](https://arxiv.org/abs/2402.14903)) for comma-grouping improving arithmetic
  does NOT have a Claude-specific replication. **Given Claude's demonstrated non-standard,
  semantic/frequency-driven digit tokenization (RQ1), do not assume comma-grouping helps Claude
  the same way it helps GPT — this is an open question (§7), not a confirmed transferable
  finding.** For prices in the codebase's actual range (e.g. XAUUSD ~2400s, USDCLP ~900s), values
  are short enough (4-5 significant digits) that thousands-grouping is largely moot anyway — the
  practical exception would be PnL/volume figures in larger units, where a decision either way
  should be tested rather than assumed.
- **Decimal truncation**: unchanged — match precision to instrument tick size; truncating below
  what's needed to distinguish adjacent values (e.g. SL/TP/entry differing only in the 3rd
  decimal) destroys information needed for MAE/MFE-vs-SL/TP reasoning.
- **Delta-encoding vs absolute prices**: absolute prices remain necessary (the model must relate
  price to SL/TP, which are absolute), but a server-computed delta column alongside the absolute
  price (mirroring `ai_context.py`'s existing `Δ={delta:+.2f}` pattern in this codebase) offloads
  arithmetic the model would otherwise attempt in-context — and per RQ1/RQ5's aggregation-
  accuracy finding, arithmetic the model attempts in-context is exactly the class of operation
  shown to be unreliable (~57-62% accuracy on aggregation/filtering tasks). This strengthens the
  original recommendation: **compute every derived numeric relationship server-side that you can
  anticipate the model needing**, rather than leaving it to be computed from raw columns.
- **Normalization**: unchanged — do not normalize/rescale absolute prices for the analysis use
  case; the model needs real levels to compare against SL/TP/S-R. LLMTime's normalization
  (percentile-based affine rescaling) is a forecasting-task technique with no motivation in an
  analysis/critique task where absolute levels are the point.
- **Sign and unit explicitness**: unchanged — always signed deltas (`+`/`-` explicit), units
  labeled once in the header, not per-cell.

*This section is INFERENCE reasoning applied to RQ1's newly-confirmed Claude-tokenizer finding
and the codebase's actual schema (`sentinel_engine/research/registry2.py`,
`sentinel_engine/ai_context.py`) — no paper directly studies delta-vs-absolute encoding for LLM
trade analysis specifically.*

### RQ4 — Multi-timeframe presentation

No paper or Anthropic doc addresses this directly. Recommendations below are INFERENCE, now
additionally grounded in Anthropic's confirmed document-structuring pattern (RQ6):

- **Coarse-to-fine, top-to-bottom**: present M15 before M5 before M2 before M1. This both
  mirrors how a human analyst reads multi-TF charts (context → detail) and exploits the
  documented start-of-context primacy effect (RQ2/RQ6) for the information most needing to
  anchor the read (higher-timeframe regime).
- **Sectioning via Anthropic's own `<document>` pattern, not interleaving**: Anthropic's fetched
  guidance (RQ6) explicitly recommends `<document index="n"><source>...</source>
  <document_content>...</document_content></document>` for wrapping each distinct data unit —
  this is directly reusable for multi-timeframe data: one `<document>` (or a domain-renamed
  equivalent, e.g. `<timeframe>`) per timeframe, each with a `source`-equivalent metadata tag
  naming the timeframe/instrument/window. Interleaving bars from different timeframes into a
  single row-per-instant table remains a clear anti-pattern (§8) — most timeframes lack a bar at
  every finer-timeframe instant, producing sparse/ragged rows, and it forces tracking which
  columns are stale vs. live with no compensating benefit.
- **Explicit alignment anchor**: mark the entry/exit bar(s) inline within each timeframe section
  (e.g. an inline `<<< ENTRY >>>` marker row), following the same pattern
  `sentinel_engine/ai_context.py` already uses for price-among-levels
  (`>>> PRECIO: ... <<<`) — gives the model a hard anchor for relative-offset reasoning instead
  of requiring cross-section timestamp correlation.
- **No silent redefinition of a column name across sections** — if a column's underlying
  computation changes between sections, rename it or state parameters in the section header.

### RQ5 — Summaries-plus-excerpts hybrids

This is the resolved, evidence-strengthened form of the team's assumption's second half. The
strongest new evidence: the TOON benchmark's task-type breakdown (RQ1) — **aggregation accuracy
~61.9%, filtering accuracy ~56.8%, versus field-retrieval accuracy 99.6%**, essentially
format-independent. This directly predicts that asking Claude to compute PF/WR/expectancy or to
filter "all trades with MAE > 90% of SL" from a raw row table is structurally unreliable — not a
fixable-by-better-formatting problem, but a fixable-by-not-asking-the-model-to-aggregate problem.
A real trading-LLM system found in this research, QuantAgent
([arXiv:2509.09995](https://arxiv.org/html/2509.09995v3)), makes exactly this architectural
choice: it does not feed raw OHLC series to its LLM agents at all — indicators/signals are
pre-computed by bound tools and the LLM reasons only over the derived values. This is a
practitioner design decision, not a benchmarked ablation, but it's independent corroboration of
the same conclusion from a real deployed system.

- **Raw-only** (no aggregation): wastes tokens on unremarkable trades, risks lost-in-the-middle/
  context-rot degradation on the majority of a large trade set, and forces the model to attempt
  exactly the aggregation-class computation shown to be weak.
- **Stats-only** (no excerpts): the model cannot ground a specific critique in real trades
  without seeing at least the flagged trades' actual price action — pushes toward generic,
  non-falsifiable commentary, and contradicts Anthropic's own "ground responses in quotes"
  guidance (RQ6), which exists specifically to reduce hallucination against long-context data.
- **Hybrid (recommended, unchanged from initial draft, now more strongly evidenced)**: full
  aggregate stats block (server-computed PF, WR, expectancy, MAE/MFE distributions, exit-reason
  breakdown) + a complete but compact one-row-per-trade summary table (no bars — safe at
  hundreds of rows since it's a fixed-column lookup task, i.e. the ~99.6%-accuracy task type,
  not the aggregation task type) + curated raw-bar excerpts for a bounded, justified subset
  (worst-N by PnL, near-miss-SL trades, trader-named trades).

### RQ6 — Anthropic-specific guidance

Sourced by direct WebFetch of official Anthropic documentation on 2026-07-12. Anthropic has
**consolidated its formerly per-technique pages (be-clear-and-direct.md, use-xml-tags.md,
long-context-tips.md, chain-of-thought.md, etc.) into a single living reference**,
["Prompting best practices"](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) —
the old per-technique URLs the task brief named are superseded by this page. This is itself a
useful fact: there is now one canonical prompt-engineering reference to track, not several.

**Document placement — data before instructions, quantified.** Direct quote:
> "Put longform data at the top: Place your long documents and inputs near the top of your
> prompt, above your query, instructions, and examples. This improves performance across all
> models."
> "Queries at the end can improve response quality by up to 30% in tests, especially with
> complex, multi-document inputs."

This resolves RQ6's placement question with a first-party, quantified figure: **dossier data
first, trader's question last.** Both position and strategy dossier templates below (§3-4) are
structured this way.

**Exact recommended XML pattern for multiple data sections.** Direct quote and verbatim example:
> "Structure document content and metadata with XML tags: When using multiple documents, wrap
> each document in `<document>` tags with `<document_content>` and `<source>` (and other
> metadata) subtags for clarity."

```xml
<documents>
  <document index="1">
    <source>annual_report_2023.pdf</source>
    <document_content>
      {{ANNUAL_REPORT}}
    </document_content>
  </document>
  <document index="2">
    <source>competitor_analysis_q2.xlsx</source>
    <document_content>
      {{COMPETITOR_ANALYSIS}}
    </document_content>
  </document>
</documents>

Analyze the annual report and competitor analysis. Identify strategic advantages and recommend Q3 focus areas.
```

This maps directly onto wrapping each timeframe's OHLCV data, each trade excerpt, etc., as a
`<document>`-equivalent block with a `source`-equivalent metadata tag — adopted directly in the
templates below (§3-4), domain-renamed (`<timeframe>`, `<trade>`) per Anthropic's own guidance
that nesting/naming should follow the data's natural hierarchy with consistent, descriptive tag
names — no fixed vocabulary is mandated.

**Quote-then-answer grounding.** Direct quote:
> "Ground responses in quotes: For long document tasks, ask Claude to quote relevant parts of
> the documents first before carrying out its task. This helps Claude cut through the noise of
> the rest of the document's contents."

With a transferable worked example (physician's-assistant pattern in the source): ask Claude to
place cited evidence in a `<quotes>`-equivalent tag before producing analysis in a separate tag.
Directly applicable: instruct Claude to cite specific bars/trade_ids relevant to its claim before
stating a critique or recommendation — this is the mechanism the mini-eval's Q8 rubric (§9)
specifically scores for.

**Context window mechanics (fetched from
[context-windows.md](https://platform.claude.com/docs/en/build-with-claude/context-windows.md)).**
- Both target models have a **1M-token context window by default, no beta header, standard
  pricing**: "Claude Opus 4.8, Claude Opus 4.7, Claude Opus 4.6, Claude Sonnet 5, and Claude
  Sonnet 4.6 have a 1M-token context window on the Claude API... For every model with a 1M-token
  context window, 1M is the default."
- **"Context rot" — Anthropic's own name for the degradation phenomenon**, directly relevant to
  RQ2: "As token count grows, accuracy and recall degrade, a phenomenon known as context rot.
  This makes curating what's in context just as important as how much space is available." The
  docs explicitly point to Anthropic's engineering blog for mechanism and mitigation (see below).
- **Everything counts toward the window, including tool definitions and cached content**:
  "Everything in the request counts toward the context window: the system prompt, every message
  in `messages`..., and your tool definitions." And: "Cached prompt prefixes still occupy the
  context window: prompt caching changes what you pay for those tokens, not whether they count."
  — relevant since this design adds `get_trade_bars`/`get_trade_detail` tool schemas as a fixed
  per-turn cost (RQ2).
- **Model-specific asymmetry relevant to the two target models**: Claude **Sonnet 5** (along with
  Sonnet 4.6/4.5, Haiku 4.5) has automatic **context awareness** — the model is told its
  remaining token budget via injected tags (`<budget:token_budget>200000</budget:token_budget>`,
  updated after tool calls) and self-moderates accordingly. **Claude Opus 4.8 does NOT receive
  this automatic injection.** For Opus, the equivalent capability is the beta **Task Budgets**
  feature (`output_config.task_budget`, per the claude-api skill's cached guidance, already
  loaded this session) — worth adopting explicitly for long, multi-turn strategy-review sessions
  on Opus if session length is a concern, since it won't self-moderate the way Sonnet 5 does by
  default.
- **Overflow behavior**: input alone exceeding the window returns 400 `invalid_request_error`
  on every model; on Claude 4.5+, input + `max_tokens` exceeding the window can instead surface
  as `stop_reason: "model_context_window_exceeded"` (a graceful stop, not a request failure) —
  worth explicit handling in any implementation per the claude-api skill's migration guidance
  already covering this stop reason.

**Prompt caching — exact mechanics for the "stable data + varying question" pattern (fetched
from
[prompt-caching.md](https://platform.claude.com/docs/en/build-with-claude/prompt-caching.md)).**
This is close to a direct spec for this app's architecture. Key mechanics:
- "Cache writes happen only at your breakpoint... a hash of the entire prefix ending at that
  block." Reads look backward through a **20-block lookback window**.
- **The exact correct placement rule, quoted**: "Place `cache_control` on the last block whose
  prefix is identical across the requests you want to share a cache." For this app: place
  `cache_control` at the end of the dossier's data section (end of `</market_context>` or
  equivalent), never on the question block — putting it on the question (which varies every
  turn) guarantees a permanent cache miss, since no prior request ever wrote a cache entry there.
- **Ordering hierarchy**: `tools` → `system` → `messages`; a change at any level invalidates that
  level and everything after it. Concretely: if tool definitions change between requests (e.g.
  toggling whether `get_trade_bars` is offered), the cached data block is invalidated too, even
  if the data itself didn't change — keep the tool set stable across a session if cache-hit rate
  matters.
- **Minimum cacheable size**: 1,024 tokens for Opus 4.8/Sonnet 5/Sonnet 4.6/4.5 (this app's own
  claude-api skill cache lists Opus 4.8 at 4,096 tokens — treat the exact number as needing
  reconciliation against the live docs at implementation time, both values were seen across
  sources during this research and the discrepancy wasn't resolved; verify via
  `cache_creation_input_tokens`/`cache_read_input_tokens` in the actual response rather than
  assuming either figure). Both the position dossier (3-8K tokens) and strategy dossier (8-20K)
  comfortably clear either threshold.

**Anthropic engineering blog — tool use vs. context-stuffing (first-party, not platform docs,
but Anthropic-authored).** ["Effective context engineering for AI
agents"](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
(Sept 29, 2025) and ["Writing effective tools for AI
agents"](https://www.anthropic.com/engineering/writing-tools-for-agents) (Sept 11, 2025) — see
RQ7 for the full synthesis; both are the single most directly-actionable sources found in this
entire research pass for the tool-vs-context question, more detailed than the platform docs.

*Sources: [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices),
[Context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows.md),
[Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching.md) — all
fetched directly 2026-07-12.*

### RQ7 — Tool use vs. context-stuffing, per use case

Anthropic's own engineering blog gives a direct, first-party framework for this tradeoff — more
specific and more current than the general platform docs.

**"Effective context engineering for AI agents"** (Sept 2025). Core tradeoff, quoted:
> "there's a trade-off: runtime exploration is slower than retrieving pre-computed data."

Recommended default, quoted:
> "the most effective agents might employ a hybrid strategy, retrieving some data up front for
> speed, and pursuing further autonomous exploration"

Worked example given (Claude Code's own architecture): `CLAUDE.md` is stuffed into context up
front; `glob`/`grep` are exposed as tools for "just-in-time" navigation beyond that. This maps
directly: a compact recent-window/summary in context up front, full bar/trade history queryable
via tool for anything beyond that window.

**"Writing effective tools for AI agents"** (Sept 2025) — the more directly actionable source
for *how* to build the drill-down tools once you decide to expose them:
> "tool implementations should take care to return only high signal information back to agents.
> They should prioritize contextual relevance over flexibility." Recommends "pagination, range
> selection, filtering, and/or truncation with sensible default parameter values for any tool
> responses that could use up lots of context."
> "For Claude Code specifically, we restrict tool responses to 25,000 tokens by default." —
> **adopt this as this app's own default ceiling** for `get_trade_bars`/`get_trade_detail`
> responses (well above the position-dossier's own 3-8K budget, giving headroom for a
> deliberately large drill-down query without needing a second round-trip).
> "directly encourage agents to pursue more token-efficient strategies, like making many small
> and targeted searches instead of a single, broad search." — worth stating explicitly in the
> tool descriptions/system prompt for the strategy-review tools.
> On format choice for tool *responses* specifically: "there is no one-size-fits-all solution...
> select the best response structure based on your own evaluation" — direct first-party backing
> for treating the mini-eval (§9) as necessary rather than optional.

**"Building Effective Agents"** (Dec 2024, older but still the canonical simplicity-first
reference): "finding the simplest solution possible, and only increasing complexity when
needed... optimizing single LLM calls with retrieval and in-context examples is usually enough."
This is the first-party justification for defaulting to context-stuffing for the bounded
position-dossier case rather than reaching for a tool architecture there too.

**Recommendation table** (unchanged conclusion from the initial draft, now backed by first-party
Anthropic sources rather than pure inference):

| | **Position dossier (1 trade)** | **Strategy review (N trades)** |
|---|---|---|
| Data size | Bounded, small (~3-8K tokens) | Unbounded in principle |
| Access pattern | Whole dossier used holistically in one read | Most trades unremarkable; only a subset needs scrutiny |
| **Recommendation** | **Context-stuffing** — "start simple," single call, no tool round trip | **Hybrid**: stats + compact trade-log table stuffed up front; `get_trade_bars(trade_id, timeframe, bars_before, bars_after)` and `get_trade_detail(trade_id)` exposed as tools, capped at 25,000 tokens/response, for anything beyond the pre-flagged excerpts |
| Rationale | Anthropic's own "usually enough" simplicity guidance; a tool round trip adds latency for data that's already small and fully known up front | Anthropic's own hybrid-strategy recommendation for data too large/exploratory to fully pre-stuff; keeps tool responses "high signal" per their tool-design guidance |

### RQ8 — Anti-patterns (concrete)

- **JSON array-of-objects for large regular tables** — worst-in-class token cost in every
  benchmark found (RQ1); repeats every key name on every row.
- **Bare CSV assumed safe by default** — **revised anti-pattern, new in this draft**: one
  rigorous benchmark found CSV as the *second-worst* format for comprehension accuracy despite
  being cheapest in tokens. Do not adopt CSV purely on the strength of "it's what everyone
  reaches for" — validate against Markdown-table specifically for this app's schema (§9) before
  committing.
- **Unaligned/ragged series** — mixing timeframes into one table where not every row has every
  column populated forces the model to distinguish missing/zero/stale with no labeling to help.
- **Mixed units without labels** — pips vs price vs percentage in an unlabeled column, or PnL
  silently switching currency/unit basis by instrument. Label units in the header, once.
- **Unlabeled columns / no header row.**
- **Redundant full timestamps per row within a fixed-cadence series** — token waste; prefer a
  relative bar-offset index, reserve full timestamps for the metadata envelope and for genuinely
  irregular-cadence markers (session/weekend gaps).
- **Asking the model to aggregate/filter over raw rows** — **strengthened anti-pattern, now with
  a specific number**: benchmarked aggregation accuracy ~61.9%, filtering ~56.8%, essentially
  format-independent (RQ1/RQ5). Compute these server-side, always.
- **Inconsistent decimal precision within a column** — breaks place-value pattern matching.
- **Normalizing/rescaling absolute prices** for a task needing the model to relate price to
  concrete SL/TP/S-R levels.
- **Full-session raw dumps "just in case"** — directly contradicted by both lost-in-the-middle
  and Anthropic's own "context rot" framing (RQ2/RQ6); always window around the event.
- **Burying the question above the data** — directly contradicted by Anthropic's own quantified
  guidance ("up to 30%" quality loss risk; RQ6) — always data first, question last.
- **Rebuilding the dossier's stable section non-deterministically** (`datetime.now()`, random
  request IDs, unsorted dict keys in the data block) — silently defeats prompt caching (RQ6);
  directly checkable against this codebase's own existing discipline, since
  `sentinel_engine/ai_context.py`'s docstring already mandates "NO `datetime.now()`, no
  wall-clock, no randomness" for reproducibility — the same discipline is now also required for
  cache-hit-rate reasons in the new dossier code.
- **Adding/removing tool definitions between turns of the same session** — invalidates the
  cached data block too, per the `tools → system → messages` cache-invalidation hierarchy (RQ6),
  even when the data itself hasn't changed. Keep the tool set stable within a session.
- **One mega tool that dumps everything** instead of narrowly-scoped tools with pagination/
  filtering/truncation and sensible defaults (RQ7) — Anthropic's own tool-design guidance
  explicitly warns against this.
- **Prose/natural-language-per-data-point encoding** (PromptCast-style: "on bar 1 the price was
  X, on bar 2 it was Y...") — token-costly, no compensating benefit for tabular numeric data, and
  PromptCast's own paper reports a specific failure mode (models mis-generating tokens after
  minus signs) as a reason to avoid ad hoc natural-language numeric embedding for negative
  values (e.g. negative PnL, negative MAE-relative-to-SL) specifically.

### RQ9 — See §6 (mini-eval design) below.

---

## 3. Recommended "Position Dossier" Template

Design goals encoded below: data-before-question with the exact Anthropic-recommended XML
pattern (RQ6), coarse-to-fine multi-TF sectioning (RQ4), **Markdown tables** for regular series
(revised from CSV per RQ1's accuracy-benchmark finding) / JSON for irregular envelope (RQ1/RQ8),
windowed not full-session (RQ2), fixed decimal precision + explicit units + server-computed
deltas (RQ3), stable/deterministic prefix for cache-ability with the breakpoint on the data
block, not the question (RQ6/RQ8), quote-grounding instruction (RQ6).

Total target budget: **~3,000–8,000 tokens**.

```
<documents>

  <document index="1">
    <source>trade_record:{trade_id}</source>
    <document_content>
    <!-- ~150-300 tokens. Small, semi-irregular (optional fields like exit_reason_source) —
         JSON is the right call here, not a repeated-row table (RQ1/RQ8). -->
    {
      "trade_id": "{trade_id}",
      "instrument": "XAUUSD",
      "side": "LONG",
      "ts_in": "2026-07-10T13:22:00Z",
      "ts_out": "2026-07-10T13:41:00Z",
      "px_in": 2415.30,
      "px_out": 2418.75,
      "sl": 2413.80,
      "tp": 2420.00,
      "volume": 0.50,
      "exit_reason": "tp_hit",
      "exit_reason_source": "broker",
      "pnl_usd": 172.50,
      "mae_pips": -4.2,
      "mfe_pips": 34.5,
      "hold_time_min": 19
    }
    </document_content>
  </document>

  <document index="2">
    <source>derived_stats:{trade_id}</source>
    <document_content>
    <!-- ~50-100 tokens. Server-computed relationships the model would otherwise have to derive
         in-context — exactly the aggregation-class computation shown to be unreliable (RQ1/RQ5). -->
    MAE as % of SL distance: 28.0% (price moved 28% of the way to stop-loss before turning favorable)
    MFE as % of TP distance: 92.6% (price reached 92.6% of the take-profit distance before final exit)
    R-multiple realized: 1.84R
    </document_content>
  </document>

  <!-- ~2,500-4,500 tokens total across timeframes. Coarse-to-fine order (RQ4). Markdown table
       with header, fixed decimal precision, relative bar index not full timestamp (RQ8),
       explicit ENTRY/EXIT anchor row markers. One <document> per timeframe (RQ4/RQ6). -->

  <document index="3">
    <source>bars:M15:{trade_id}:bars_before_entry=10:bars_after_exit=6</source>
    <document_content>
    | idx | time  | open    | high    | low     | close   | ema8    | ema20   | sar     | rsi14 |
    |----:|-------|--------:|--------:|--------:|--------:|--------:|--------:|--------:|------:|
    | -10 | 12:15 | 2412.10 | 2413.40 | 2411.80 | 2413.10 | 2412.90 | 2411.50 | 2410.20 | 54.2  |
    | ... | ...   | ...     | ...     | ...     | ...     | ...     | ...     | ...     | ...   |
    | 0   | 13:15 | 2414.80 | 2415.60 | 2414.50 | 2415.30 | 2414.70 | 2412.80 | 2411.90 | 58.1  | <<< ENTRY BAR
    | ... | ...   | ...     | ...     | ...     | ...     | ...     | ...     | ...     | ...   |
    | +6  | 14:15 | 2418.20 | 2419.10 | 2417.90 | 2418.75 | 2417.50 | 2414.10 | 2413.00 | 63.4  | <<< EXIT BAR
    </document_content>
  </document>

  <document index="4">
    <source>bars:M1:{trade_id}:bars_before_entry=20:bars_after_exit=20</source>
    <document_content>
    | idx | time  | open    | high    | low     | close   | ema8    | ema20   | sar     | rsi14 |
    |----:|-------|--------:|--------:|--------:|--------:|--------:|--------:|--------:|------:|
    | -20 | 13:02 | 2414.10 | 2414.30 | 2413.90 | 2414.20 | 2414.05 | 2413.80 | 2413.50 | 51.0  |
    | ... | ...   | ...     | ...     | ...     | ...     | ...     | ...     | ...     | ...   |
    | 0   | 13:22 | 2415.10 | 2415.35 | 2415.05 | 2415.30 | 2415.00 | 2413.90 | 2413.20 | 57.8  | <<< ENTRY BAR
    | ... | ...   | ...     | ...     | ...     | ...     | ...     | ...     | ...     | ...   |
    | +19 | 13:41 | 2418.60 | 2418.80 | 2418.50 | 2418.75 | 2417.90 | 2415.20 | 2414.50 | 64.0  | <<< EXIT BAR
    </document_content>
  </document>

  <!-- ~50-150 tokens, only if a signal-panel/semaphore state exists for this trade. Irregular/
       optional per-bar → JSON, not tabular (RQ1/RQ8). Omit the whole <document> if unused. -->
  <document index="5">
    <source>signal_panel_at_entry:{trade_id}</source>
    <document_content>
    {"direction": "bull", "semaphore": "green", "layers": {"trend": 0.72, "momentum": 0.61, "structure": 0.55}}
    </document_content>
  </document>

</documents>

<!-- Place a cache_control breakpoint at the end of </documents> in the actual API request
     (RQ6) — this whole block is then a stable, cacheable prefix; only the instructions/question
     below vary across follow-up turns in the same chat. -->

<instructions>
Before answering, quote the specific bars, indicator values, or trade-record fields your
conclusion depends on. Then answer the question below, grounded in those quotes.
</instructions>

<question>
{trader's actual question, e.g. "Was this SL too tight given the M1 volatility before entry?"}
</question>
```

Notes:
- `idx` is bar offset relative to entry (0 = entry bar), not a raw sequence number — avoids
  redundant full timestamps per row (RQ8); `time` is HH:MM only since the date is in
  `trade_record.ts_in`/`ts_out`.
- The `<instructions>` quote-grounding block directly implements Anthropic's documented "ground
  responses in quotes" recommendation (RQ6) and is the mechanism the mini-eval's Q8 rubric scores.
- Decimal precision fixed per instrument (XAUUSD `%.2f` here; a JPY pair would differ) — driven
  by tick size, not a global constant (RQ3).
- If the position is still open (out of scope per the task brief, noted for forward
  compatibility): replace `bars_after_exit` with `bars_to_now` and drop the EXIT marker.

---

## 4. Recommended "Strategy Review Dossier" Template

Design goals: stats-first with server-computed aggregates (RQ5), compact full-trade-list table
(never asks the model to aggregate — RQ1/RQ5), curated raw excerpts only for a bounded flagged
subset (RQ5), tool-use hooks for on-demand drill-down capped at 25,000 tokens/response per
Anthropic's own Claude Code default (RQ7), data-before-question (RQ6).

Total target budget: **~8,000–20,000 tokens** for the stuffed portion; unbounded additional tool
round trips available on demand.

```
<documents>

  <document index="1">
    <source>aggregate_stats:{strategy_id}:{variant_id}:{run_id}</source>
    <document_content>
    <!-- ~200-400 tokens. O(1) cost regardless of trade count. Server-computed — never derived
         by the model from raw rows (RQ1/RQ5: aggregation accuracy ~62% if left to the model). -->
    Period: {periodo_desde} to {periodo_hasta} | N trades: 187
    Profit factor: 1.62 | Win rate: 47.6% | Expectancy/trade: +$12.40
    Payoff ratio (avg win / avg loss): 1.78 | Max drawdown: -$840.00 (-8.2%) | Sharpe: 1.11

    Exit reason breakdown:
      tp_hit: 61 (32.6%) | sl_hit: 74 (39.6%) | manual_close: 38 (20.3%) | timeout: 14 (7.5%)

    MAE distribution (% of SL distance, all trades):
      0-25%: 82 | 25-50%: 51 | 50-75%: 31 | 75-100%: 15 | >100% (slippage): 8

    MFE distribution (% of TP distance, all trades):
      0-25%: 44 | 25-50%: 38 | 50-75%: 29 | 75-100%: 35 | >100% (ran past TP before exit): 41
    </document_content>
  </document>

  <document index="2">
    <source>trade_log:{run_id}:n=187</source>
    <document_content>
    <!-- ~3,500-5,000 tokens at 200 trades (Markdown table, ~18-25 tokens/row). No bars.
         Fixed-column lookup task (~99.6% accuracy per RQ1/RQ5), safe even at hundreds of rows. -->
    | trade_id | ts_in       | side  | hold_min | px_in   | px_out  | sl_dist_pips | tp_dist_pips | pnl_usd | mae_pct_sl | mfe_pct_tp | exit_reason |
    |----------|-------------|-------|---------:|--------:|--------:|-------------:|-------------:|--------:|-----------:|-----------:|-------------|
    | T00142   | 07-01 09:14 | LONG  | 12       | 2401.10 | 2403.85 | 15.0         | 42.0         | +68.75  | 18%        | 71%        | tp_hit      |
    | T00143   | 07-01 10:03 | SHORT | 4        | 2404.20 | 2405.90 | 15.0         | 42.0         | -42.50  | 112%       | 8%         | sl_hit      |
    | ...      | ...         | ...   | ...      | ...     | ...     | ...          | ...          | ...     | ...        | ...        | ...         |
    </document_content>
  </document>

  <!-- Variable, ~1,000-3,000 tokens depending on how many trades are flagged. Curated, bounded
       selection (RQ5) — worst N by PnL, near-miss-SL trades (mae_pct_sl > 90%), trader-named
       trades. NOT all trades — one <document> per flagged trade, same shape as the position
       dossier's bars/trade_record documents (RQ6 nesting-by-hierarchy). -->

  <document index="3">
    <source>flagged_trade:T00143:reason=worst_pnl_rank_1</source>
    <document_content>
      {trade_record JSON, same shape as position dossier §3}
      | idx | time | open | high | low | close | ema8 | ema20 | sar |
      |...bars table, same shape as position dossier §3...|
    </document_content>
  </document>
  <!-- ...repeat <document> per flagged trade... -->

</documents>

<!-- cache_control breakpoint at the end of </documents>. Declare get_trade_bars and
     get_trade_detail as real Claude API tool definitions (tools=[...]), not prompt text —
     capped at 25,000 tokens/response per Anthropic's own Claude Code default (RQ7). Keep the
     tool set identical across turns of the same review session — adding/removing a tool
     invalidates the cached data block too (RQ6/RQ8). -->

<instructions>
Before answering, quote the specific trades (by trade_id) or bars your conclusion depends on.
If you need bar-level detail for a trade not included above, call get_trade_bars. Do not
recompute profit factor, win rate, or other aggregate statistics yourself — cite the numbers
in aggregate_stats directly.
</instructions>

<question>
{trader's actual question, e.g. "Propose an improved SL for this variant."}
</question>
```

Notes:
- The explicit "do not recompute... cite directly" instruction is a direct, actionable
  mitigation for the aggregation-accuracy weakness documented in RQ1/RQ5 — worth testing in the
  mini-eval as its own variable (does the instruction measurably reduce recomputation attempts).
- If `n_trades` grows very large (many hundreds+), consider paginating `<trade_log>` itself
  behind a tool call too, keeping only `<aggregate_stats>` and a small "most extreme N" slice
  stuffed by default — flagged as an open scaling question (§7), no threshold established here.

---

## 5. Do / Don't Checklist

**Do:**
- Put the full data dossier before the trader's question, every time — Anthropic's own tested
  figure is "up to 30%" quality improvement from this ordering alone.
- Default to **Markdown tables** with a header row for OHLCV/indicator series and the
  strategy-review per-trade summary table; validate against bare CSV empirically for this app's
  specific schema before assuming CSV is safe (one benchmark found CSV the second-worst format
  for comprehension accuracy despite being cheapest in tokens).
- Use compact JSON only for small, irregular, or one-off structures (trade metadata, signal-panel
  snapshots) — never for large regular numeric tables, where it is worst-in-class on tokens in
  every benchmark found.
- Wrap each distinct data unit in Anthropic's documented `<document><source>...
  <document_content>...</document_content></document>` pattern (or a consistent, descriptive
  domain-renamed equivalent).
- Fix decimal precision per instrument/column, driven by tick size, held constant throughout.
- Window raw bars around entry/exit (event-centered); never dump a full session.
- Present multiple timeframes in separate, clearly-labeled document sections, coarse-to-fine,
  never interleaved into one table.
- Mark the entry/exit bar explicitly with an inline anchor.
- Compute aggregate stats (PF, WR, expectancy, MAE/MFE distributions, R-multiples) server-side
  in Python and cite them as ground truth — never ask the model to compute or recompute these
  from raw rows (benchmarked aggregation accuracy is only ~62% even on well-formatted data).
- Instruct the model explicitly to quote/cite specific bars or trade_ids before producing
  analysis (Anthropic's own "ground responses in quotes" recommendation).
- Curate raw-bar excerpts for the strategy-review case to a bounded, justified subset.
- Keep the dossier's data section byte-for-byte deterministic across repeated builds for the
  same trade/run, with the cache_control breakpoint on the LAST block of that stable data — never
  on the question block.
- Keep the tool set (if any) identical across turns of the same session — changing it
  invalidates the cached data prefix too.
- Cap tool-response size (e.g. `get_trade_bars`) at a sensible ceiling — Anthropic's own Claude
  Code default is 25,000 tokens; adopt or justify a different number.

**Don't:**
- Don't put the question before the data.
- Don't assume CSV is the safe default purely on token-cost grounds — validate accuracy too.
- Don't serialize OHLCV/indicator series as JSON-array-of-objects.
- Don't force irregular per-bar data into rigid tabular columns.
- Don't mix decimal precision within a column.
- Don't normalize/rescale absolute prices for analysis tasks.
- Don't dump a full session's bars "just in case" — window it.
- Don't interleave multiple timeframes into a single row-per-instant table.
- Don't repeat full ISO timestamps on every row of a constant-cadence series.
- Don't ask the model to compute PF/WR/expectancy/filters from raw trade rows in-context —
  this is a benchmarked weak point (~57-62% accuracy), not a stylistic preference.
- Don't stuff bar-level detail for every trade in a strategy review — bounded curation only.
- Don't embed `datetime.now()`, random IDs, or non-deterministic ordering into the dossier's
  data section.
- Don't add or remove tool definitions mid-session if cache-hit rate matters.
- Don't build one mega tool that returns everything unfiltered — narrowly-scoped tools with
  pagination/filtering/truncation and sensible size caps.
- Don't use a tool-call round trip for the single-position dossier — it's small enough to stuff
  directly.
- Don't assume any GPT-oriented digit-formatting trick (comma-grouping, digit-spacing) transfers
  to Claude unmodified — Claude's tokenizer behaves differently and this is an unvalidated gap
  (§7), not a settled transfer.

---

## 6. Mini-Eval Design

Goal: empirically validate/refute the format choices above on this codebase's actual data before
committing to one format in production — explicitly warranted by Anthropic's own guidance that
"there is no one-size-fits-all solution" for data-format choice (RQ7) and by the fact that two
independent benchmarks in this research disagreed on whether CSV is safe (RQ1).

**Design**: fix a set of 8 questions with objectively-derivable correct answers from a real (or
realistic synthetic) closed trade + surrounding bars, and a small strategy run (~30-50 trades,
small enough to hand-verify all ground truth). Render the SAME underlying data in 4 competing
formats, ask each question against each format, score against ground truth — isolates format
effect from data-selection effect.

**Formats to compare** (4 arms, revised from the initial draft to directly test the RQ1
disagreement):
1. **Markdown-table-sectioned** (this report's recommended template, §3/§4).
2. **CSV-sectioned** (structurally identical to arm 1, swap Markdown `|` syntax for bare CSV —
   the direct head-to-head this report's own evidence couldn't resolve without app-specific
   testing).
3. **JSON-array-of-objects** (the team's original assumption's "loser" arm — include to confirm
   or refute the token-cost-vs-accuracy tradeoff directly on this app's data).
4. **Stats-only, no raw bars** (drop the bars/flagged-excerpt documents entirely, keep only
   trade_record/aggregate_stats/trade_log — tests whether raw excerpts are actually load-bearing
   for the questions that need them, per RQ5's hybrid recommendation, and isolates the
   aggregation-accuracy question from the format question).

**Questions (8)** — each must have one unambiguous correct answer computable from the underlying
data, independent of the model:

*Position-dossier questions (single-trade fixture):*
1. "What was the MAE as a percentage of the stop-loss distance?" (numeric extraction/citation,
   not model-computed math — the value is already server-computed and present in the dossier).
2. "Which bar (relative to entry) had the highest high in the M1 window shown?" (row-level
   lookup/comparison across a table — the task type benchmarked at ~99.6% in the TOON study;
   should be near-perfect in every arm if the format itself isn't the bottleneck).
3. "Was EMA8 above or below EMA20 at the moment of entry?" (cross-column comparison at a
   specific, anchor-marked row).
4. "How many M1 bars elapsed between entry and the bar where price first reached its most
   favorable excursion (MFE)?" (multi-row scan + anchor-relative counting — closer to the
   filtering/aggregation task type (~57-62% benchmarked accuracy) than pure lookup; the question
   most likely to separate formats and to fail even in the best-performing arm).

*Strategy-review questions (~30-50 trade fixture):*
5. "What is the strategy's profit factor?" (control question — should be trivially correct in
   every arm since it's verbatim in `aggregate_stats`; a wrong answer here indicates a basic
   extraction failure, not a subtle format effect).
6. "How many trades were closed via sl_hit vs tp_hit?" (tests reading the exit-reason breakdown
   directly, OR — in the stats-only-denied arm 4 variant if that block is also withheld —
   counting from the trade log; use to separately test the model's aggregation reliability when
   forced to compute from raw rows vs. when handed the pre-computed answer).
7. "Which trade_id had the worst MAE-to-SL ratio, and what were its entry/exit prices?" (tests
   whether the model can identify AND cite specifics for the worst outlier — the direct test of
   the flagged-excerpt hybrid design; arms 1-3 should succeed if the excerpt is included, arm 4
   should fail or hedge since it lacks bar detail). Run a follow-up variant asking about a trade
   deliberately **outside** the pre-flagged set, to test whether the model correctly identifies
   it needs more data (tool-use fallback in the real implementation) rather than confabulating.
8. "Propose one concrete parameter change (e.g. wider SL) and justify it using at least two
   specific trades from the data." (open-ended critique-quality question, scored qualitatively —
   tests whether the format enables *grounded* recommendations, i.e. whether the model cites
   real trade_ids/prices per the quote-grounding instruction (§3-4) rather than giving generic
   advice).

**Scoring rubric**:
- Q1-3, 5-7: exact-match or tolerance-banded numeric/categorical scoring (MAE% within ±1 point,
  bar index exact, trade_id exact) — automatable, 1/0 per question per format.
- Q4: exact-match on bar count; note whether the model showed its counting method (partial
  credit for right-method-wrong-by-one vs. confabulated).
- Q8: rubric-scored 0-3 — 0 = generic/no data cited, 1 = cites a real number but not tied to a
  specific trade, 2 = cites ≥1 real trade_id with correct specifics, 3 = cites ≥2 real trades
  with correct specifics AND a mechanically coherent recommendation.
- Per-format score = mean over the 8 questions (Q1-7 binary/partial, Q8 normalized 0-1). Report
  the per-question breakdown, not just the aggregate — given this research found genuinely
  conflicting evidence on CSV specifically (RQ1), the eval's primary deliverable is resolving
  that disagreement for this app's actual data, not just producing one aggregate winner.
- Track token count per format per question via `count_tokens` (never `tiktoken` — see the
  claude-api skill's token-counting guidance) alongside the accuracy score, to report a
  cost-accuracy tradeoff table.
- Run each (format × question) combination **at least 3 times** at fixed settings (e.g.
  `effort: "high"` on Claude Opus 4.8) and take the majority/median result — single-sample
  scoring cannot distinguish a real format effect from run-to-run variance, especially for Q4
  and Q8.
- Run the same 8-question × 4-format matrix against **both** target models (Opus 4.8 and Sonnet
  5) if budget allows — this research found a real, first-party-documented behavioral difference
  between them (Sonnet 5's automatic context-awareness injection vs. Opus 4.8's lack thereof;
  RQ6) that could plausibly interact with format choice on longer strategy-review prompts.

**Out of scope for the mini-eval** (explicitly deferred): multi-timeframe coarse-to-fine
ordering (RQ4) and windowing-size tuning (RQ2's N=20/M=20 defaults) are separate, larger
experiments — this mini-eval fixes those choices as constants and only varies serialization
format, per RQ9's framing.

---

## 7. Open Questions

1. **What is the actual optimal window size (N bars before entry / M bars after exit)?** N=20/
   M=20 at entry TF is a starting default with no empirical backing specific to this app.
2. **Does Claude's tokenizer exhibit any residual digit-boundary issue on 4-5 significant-digit
   prices (e.g. XAUUSD ~2400-2450), and does GPT-oriented comma-grouping advice help, hurt, or
   do nothing for Claude specifically?** This report found strong evidence that Claude's
   tokenizer behaves differently from both GPT and LLaMA (semantic/frequency-driven digit
   grouping, not a fixed rule) but found **no controlled study of Claude + numeric-formatting-
   choice + downstream accuracy** — this is the most significant unresolved evidence gap in the
   whole report and worth a targeted micro-check (`count_tokens` + manual token-boundary
   inspection on a real price column, ideally paired with a small accuracy check) before
   finalizing precision/grouping choices.
3. **At what trade count does the strategy-review dossier's `<trade_log>` itself need to move
   behind a tool call instead of being stuffed?** Unresolved; no threshold established.
4. **Should signal-panel/semaphore data be included in the position dossier by default, or only
   on request?** Treated as optional (small cost when present) but not established to measurably
   help position-level critique quality.
5. **Multi-position / multi-symbol correlation context**: `ai_context.py`'s existing live-signal
   format includes cross-asset correlation (DXY, copper, WTI, etc.) with no analog yet in the
   proposed dossiers. Whether/how to fold cross-asset context into a *post-hoc* position critique
   (vs. the *live* trading-signal context `ai_context.py` currently serves) is unresolved and out
   of scope here.
6. **Minimum cacheable prefix size for Opus 4.8 — 1,024 or 4,096 tokens?** This research
   surfaced both figures across different sources (live platform docs vs. the claude-api skill's
   cached reference) without reconciling them. Verify empirically via
   `cache_creation_input_tokens`/`cache_read_input_tokens` at implementation time rather than
   assuming either number; either way both dossier size classes should clear the threshold.
7. **Does prompt caching actually pay off for the position-dossier size class in practice**,
   given it sits close to whichever minimum-cacheable-prefix figure turns out correct? Needs
   direct measurement once the real endpoint exists.
8. **No peer-reviewed 2025-2026 paper was found that directly supersedes LLMTime for LLM-based
   time-series *analysis* (as opposed to *forecasting*) serialization**, and **no study was found
   that directly tests OHLCV-specific serialization format choice** — the closest evidence is
   general tabular-format benchmarks (not time-series-specific) and general forecasting-oriented
   papers (not analysis-oriented). Both gaps are explicitly flagged rather than papered over;
   the practitioner pattern found in real trading-LLM systems (QuantAgent, Narrata: pre-compute
   indicators/summaries, don't feed raw OHLC to the LLM) is corroborating but not a substitute
   for a controlled ablation.
9. **The CSV-vs-Markdown-table accuracy disagreement between the two practitioner benchmarks
   found (RQ1) is the single most actionable open question** — it is exactly what the mini-eval
   (§9) is designed to resolve for this app's specific data, and this report deliberately does
   not treat either benchmark as final.

---

## Appendix: Sources Consulted

**Peer-reviewed / arXiv:**
- Gruver, N. et al. "Large Language Models Are Zero-Shot Time Series Forecasters." NeurIPS 2023.
  [arXiv:2310.07820](https://arxiv.org/abs/2310.07820)
- Jin, M. et al. "Time-LLM: Time Series Forecasting by Reprogramming Large Language Models."
  ICLR 2024. [arXiv:2310.01728](https://arxiv.org/abs/2310.01728)
- Xue, H. & Salim, F. "PromptCast: A New Prompt-based Learning Paradigm for Time Series
  Forecasting." IEEE TKDE. [arXiv:2210.08964](https://arxiv.org/abs/2210.08964)
- "Tokenization counts: the impact of tokenization on arithmetic in frontier LLMs."
  [arXiv:2402.14903](https://arxiv.org/abs/2402.14903)
- Nogueira, R. et al. "Investigating the Limitations of Transformers with Simple Arithmetic
  Tasks." [arXiv:2102.13019](https://ar5iv.labs.arxiv.org/html/2102.13019)
- Liu, N. F. et al. "Lost in the Middle: How Language Models Use Long Contexts" (secondary
  summaries consulted; original replicated across GPT-3.5, GPT-4, Claude 1.3, LongChat-13B,
  MPT-30B, Cohere Command).
- "Found in the Middle" (Ms-PoE mitigation). [arXiv:2403.04797](https://arxiv.org/pdf/2403.04797)
- QuantAgent: Price-Driven Multi-Agent LLMs for High-Frequency Trading.
  [arXiv:2509.09995](https://arxiv.org/html/2509.09995v3)
- Additional leads noted but not deep-verified: TQA-Bench
  ([arXiv:2411.19504](https://arxiv.org/pdf/2411.19504)), TradExpert
  ([arXiv:2411.00782](https://arxiv.org/html/2411.00782v2)), "Do VLMs Truly Read Candlesticks?"
  ([arXiv:2604.12659](https://arxiv.org/html/2604.12659v1)).

**Official Anthropic (fetched directly, 2026-07-12):**
- [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
  (consolidated replacement for the formerly-separate long-context-tips.md / use-xml-tags.md /
  chain-of-thought.md pages)
- [Context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows.md)
- [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching.md)
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  (Anthropic engineering blog, Sept 29, 2025)
- [Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
  (Anthropic engineering blog, Sept 11, 2025)
- [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
  (Anthropic research blog, Dec 19, 2024)
- Claude API skill (first-party, loaded this session): `shared/prompt-caching.md`,
  `shared/agent-design.md`, `shared/tool-use-concepts.md`, `shared/models.md`
- `github.com/anthropics/claude-cookbooks` (renamed from `anthropic-cookbook`) — no notebook
  found specifically scoped to long-context financial time-series; closest adjacent examples are
  `tool_use/tool_search_with_embeddings.ipynb` (finance-domain tool definitions, tangential),
  `misc/prompt_caching.ipynb`, `misc/how_to_make_sql_queries.ipynb` (query-on-demand pattern as
  an alternative to context-stuffing for large histories).

**Practitioner / independent benchmarks (weight below peer-reviewed/official; cited individually
per-claim in the body above rather than treated as a single aggregated source):**
- [artfish.ai — Claude/GPT/LLaMA/Mixtral/Gemma tokenizer comparison](https://www.artfish.ai/p/how-would-you-tokenize-or-break-down)
- [improvingagents.com — 11-format table benchmark](https://www.improvingagents.com/blog/best-input-data-format-for-llms/)
- [TOON format benchmarks](https://toonformat.dev/guide/benchmarks) and
  [improvingagents.com TOON writeup](https://www.improvingagents.com/blog/toon-benchmarks/)
  (4-model benchmark including Claude Haiku 4.5)
- [jangwook.net — token-cost-only format experiment](https://jangwook.net/en/blog/en/llm-token-cost-data-format-experiment/)
- [emergentmind.com — context degradation summary](https://www.emergentmind.com/topics/context-degradation-in-llms)

**Codebase grounding (this repo, read directly, not web-sourced):**
- `sentinel_engine/ai_context.py` — existing live-signal AI context format (precedent for
  section-header style, explicit signed deltas, entry-anchor markers; documented determinism
  discipline directly reused as the cache-hit-rate justification in §RQ8/checklist)
- `sentinel_engine/research/registry2.py` — `trade` and `run` table schemas (exact field names
  used in the templates: `ts_in`, `ts_out`, `px_in`, `px_out`, `sl`, `tp`, `exit_reason`, `pnl`,
  `mae`, `mfe`; `run.pf`, `run.wr`, `run.payoff`, `run.maxdd`, `run.sharpe`)
- `docs/superpowers/specs/2026-07-07-P2-P3-parallel-ownership.md` — confirms no existing
  chat/LLM-context design doc for this feature yet as of this report's date
