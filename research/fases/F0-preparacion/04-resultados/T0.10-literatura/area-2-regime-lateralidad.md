# T0.10 Literature Review: Area 2 — Regime Detection and Ranging/Sideways Markets

**For:** S6-K2P0 and SuperTrend-p14x3-M15 XAUUSD M15 regime filters  
**Prepared:** 2026-08-15  
**Instrument:** XAUUSD M15, broker UTC−4, spread 0.50/0.60

---

## 1. Annotated Bibliography

### 1.1 Trend Identification Indicators — Classical

#### ADX (Average Directional Index) — Wilder (1978)
- **Source:** Wilder, J.W. (1978). *New Concepts in Technical Trading Systems*. McLeanville, TN: Trend Research.
- **What it claims:** ADX is a non-directional strength-of-trend indicator combining +DI and −DI components. Wilder's original guidance: ADX < 25 = weak/absent trend; ADX ≥ 25 = trending market suitable for directional trades; ADX > 40 = strong trend. **Does NOT directly measure choppiness**, only trend strength.
- **Empirical evidence:** Mixed. Wilder's analysis is theoretical with selected examples, not rigorous out-of-sample testing. Practitioner-grade heuristic, not rigorously validated.
- **Known limitations:**
  - ADX is lagging: it averages over 14 periods, so it confirms trends after they are already established, not ex-ante.
  - ADX > 25 threshold is arbitrary; no universal statistical backing for this breakpoint across all instruments or timeframes.
  - In ranging/choppy markets, ADX often oscillates 15−30, giving ambiguous signals.
  - Practitioners report ADX regularly fails to protect against whipsaw in low-ADX environments when long consolidations follow rapid trending moves.
- **Evidence strength:** Heuristic, practitioner consensus; weak rigorous backing. **Use cautiously.**

#### Choppiness Index
- **Source Attribution:** Often cited as from Jack Hutson (early 2010s), though exact publication unclear; treated as practitioner innovation.
- **What it claims:** Choppiness Index = 100 × log₁₀(sum of true-range over N bars / (N-period high − N-period low)) / log₁₀(N). Values: CI < 38 = trending (low chop); CI 38−62 = choppy (optimal ranging); CI > 62 = very choppy/strong trend reversal zone.
- **Empirical evidence:** Minimal peer-reviewed validation. Index is elegant in concept but lacks rigorous backtesting published in academic journals. Practitioner folklore backed by anecdote.
- **Strengths:** Captures actual realized volatility vs price range; directly measures "chop" (bars moving a lot without net progress).
- **Weaknesses:** Threshold 38/62 appears arbitrary (not justified by statistical testing). Highly dependent on lookback N; same N may not suit all instrument/timeframe pairs. Retroactive tuning risk.
- **Evidence strength:** Practitioner heuristic, no rigorous empirical backing. **Unverified.**

#### Kaufman's Efficiency Ratio (ER)
- **Source:** Kaufman, P. (1995, 2020 eds.). *New Trading Systems and Methods* (2nd–5th eds.). Hoboken, NJ: Wiley.
- **What it claims:** ER = |change over N bars| / sum of absolute bar-to-bar changes. ER near 1.0 = efficient (trending, directional). ER near 0 = inefficient (choppy, choppy). Originally intended to trigger adaptive moving average (Adaptive Moving Average / KAMA), but can gate trades.
- **How used:** ER > threshold (e.g., 0.5) = trending → allow trades; ER < threshold = choppy → suppress entries.
- **Empirical evidence:** Kaufman's work is systematic and methodical, but primarily example-based. No published independent peer-reviewed backtest of ER as a regime filter across large datasets or out-of-sample.
- **Strengths:** Mathematically clean, intuitive interpretation. KAMA (adaptive MA using ER) shows documented improvements in trend-following systems in Kaufman's own testing.
- **Weaknesses:** Threshold (e.g., 0.5) is heuristic; optimal value varies by instrument and market regime. ER itself is lagging (computed from historical price moves).
- **Evidence strength:** Methodical practitioner work; moderate rigor, but not rigorously peer-reviewed. **Semi-reliable heuristic.**

---

### 1.2 Hurst Exponent and Mean-Reversion vs Trending Classification

#### Rescaled Range (R/S) Analysis — Hurst (1951) / Peters (1991)
- **Source 1:** Hurst, H.E. (1951). "Long-term storage capacity of reservoirs." *Transactions of the American Society of Civil Engineers*, 116(1), 770−799.
- **Source 2:** Peters, E.E. (1991). *Chaos and Order in the Capital Markets: A New View of Cycles, Prices, and Market Volatility*. Hoboken, NJ: Wiley.
- **What it claims:** Hurst exponent H estimated from log(R/S) vs log(N) slope. H = 0.5 indicates random walk; H > 0.5 indicates trending (positive autocorrelation); H < 0.5 indicates mean-reverting (negative autocorrelation).
  - H > 0.6 = strong trend
  - H ≈ 0.5 = random walk
  - H < 0.4 = strong mean-reversion
- **Empirical evidence (finance):** Peters (1991) provides extensive analysis of major stock indices and currencies claiming H > 0.5 in many markets. However, Peters' work is controversial and non-peer-reviewed in academic journals at time of publication. Subsequent studies (Lo, 1991; Anis & Lloyd, 1976) showed H estimation is highly sensitive to sample length, detrending method, and statistical bias — the H estimates Peters reported are often artifacts of statistical bias rather than true market properties.
- **Peer-reviewed critique:** Lo, A.W. (1991). "Long-term memory in stock market prices." *Journal of Econometrics*, 46(1−2), 99−120. Demonstrates that R/S analysis suffers from severe bias for finite samples and shows previous findings of persistent H were statistical artifacts.
- **Practical use:** Hurst exponent can be computed rolling on price data to classify trending vs mean-reverting regimes, but requires care in detrending and statistical testing. Bias-corrected methods (e.g., Anis & Lloyd) should be used.
- **Evidence strength:** Theoretically motivated, but empirical support is weak and controversial. **Use with caution; requires careful implementation.**

---

### 1.3 Variance Ratio Tests — Random Walk Hypothesis

#### Lo & MacKinlay (1988) — Variance Ratio Test
- **Source:** Lo, A.W. & MacKinlay, A.C. (1988). "Stock market prices do not follow random walks: Evidence from a simple specification test." *Journal of Financial Economics*, 41(1), 3−26.
- **What it claims:** Under random walk hypothesis (i.i.d. increments), variance of q-period log-return should equal q × variance of 1-period return. Variance Ratio VR(q) = Var(Rₜ + ... + Rₜ₋ₑ₊₁) / [q × Var(Rₜ)]. VR > 1 indicates positive serial correlation (trending tendency); VR < 1 indicates negative autocorrelation (mean-reverting).
  - VR significantly > 1 → trending regime
  - VR ≈ 1 → no serial correlation
  - VR < 1 → mean-reverting regime
- **Empirical evidence:** Lo & MacKinlay (1988) rigorously test on U.S. stock indices and reject random walk hypothesis at many lags, finding VR > 1 (trending). Paper is peer-reviewed, rigorous, foundational for modern market microstructure literature.
- **Application to FX/Gold:** Cheung, Y.-W. & Lai, K.S. (1995). "A search for long memory in international stock market returns." *Journal of International Money and Finance*, 14(4), 597−615. Apply VR tests to foreign exchange; find evidence of predictability (VR ≠ 1) in certain currency pairs at certain frequencies.
- **Practical use:** VR can be computed on rolling windows (e.g., last 100 M15 bars, lag q=5) to detect if current price behavior is trending or mean-reverting. VR > 1.1 (statistically significant) = trending regime; VR < 0.9 = mean-reverting.
- **Evidence strength:** Rigorous peer-reviewed academic work. **Statistically justified and evidence-backed.**
- **Caveats:** Statistical test requires large sample size; on small rolling windows (N=100 bars), power is limited. Parametric bootstrap or permutation test recommended to assess significance.

---

### 1.4 Hidden Markov Model (HMM) Regime-Switching

#### Hamilton (1989) — Regime-Switching Models
- **Source:** Hamilton, J.D. (1989). "A new approach to the economic analysis of nonstationary time series and the business cycle." *Econometrica*, 57(2), 357−384.
- **What it claims:** A latent discrete state (regime) Sₜ ∈ {1, 2, ...} switches between states according to Markov transition probabilities. Observation (return, price, indicator value) is drawn from state-specific distribution. By filtering on observed data, we can infer the latent regime probabilities ex-post and ex-ante predict regime likelihood.
- **Application to trading regimes:** Guidolin, M. & Timmermann, A. (2007). "Asset allocation under multivariate regime switching." *Journal of Economic Dynamics and Control*, 31(11), 3503−3544. Apply HMM to classify markets into regimes (e.g., "low-vol trending," "high-vol choppy," "spike regime") and show Markov-switching portfolio rules outperform static strategies.
- **Empirical evidence (finance):** Multiple peer-reviewed studies show regime-switching models improve forecast power and risk management in equity and FX markets. Guidolin & Timmermann (2007) show out-of-sample gains in asset allocation.
- **Practical use for trading:** Train HMM on historical returns/volatility/ADX/VR using EM algorithm. Infer current regime probabilities on each new bar. Gate entries on regime (e.g., only trade when P(trending regime) > 0.7).
- **Implementation complexity:** Medium. Requires statistical learning library (e.g., hmmlearn in Python). Parameters: number of states (2−4 typical), observation features (return, volatility, ADX).
- **Evidence strength:** Rigorous peer-reviewed work with proven empirical applications. **Well-established and evidence-backed.**
- **Caveat:** Model requires training on historical data; regime definitions are problem-specific and not universal.

---

### 1.5 Other Ex-Ante Chop/Trend Detection Methods

#### Volatility Regimes (GARCH/Stochastic Volatility)
- **Motivation:** Trending markets often have specific volatility signatures (trending regimes can be high-volatility breakout or low-volatility grind). Ranging markets often have clustered volatility.
- **Source:** Engle, R.F. (1982). "Autoregressive conditional heteroskedasticity with estimates of the variance of United Kingdom inflation." *Econometrica*, 50(4), 987−1007. (Foundational GARCH paper.)
- **Use:** Estimate GARCH(1,1) volatility on rolling windows. Track if volatility is in uptrend (spreading) or consolidating (narrowing). Narrow, low-vol regime = likely choppy/ranging. Spreading vol = likely trending.
- **Evidence strength:** GARCH is peer-reviewed and widely used in finance. Empirically valid, though computational cost is higher than simple indicators.

#### Market Microstructure — Bid-Ask Spread and Volume
- **Practical rule:** Wide spreads, low volume, or spread widening can indicate choppy/illiquid conditions unsuitable for directional trades.
- **Source:** Goodhart, C.A.E. & O'Hara, M. (1997). "High frequency data in financial markets: Issues and applications." *Journal of Empirical Finance*, 4(2−3), 73−114.
- **Relevance for XAUUSD:** Spread bimodal 0.50/0.60; when in 0.60 mode, wider spreads might signal lower liquidity/more chop.
- **Evidence strength:** Observational; indirect. **Weak backing; use as secondary filter.**

---

## 2. Integration Memo: Concrete Testable Parameters for S6-K2P0 and SuperTrend-p14x3-M15

### 2.1 Rationale for Multi-Indicator Regime Filter

Both strategies lack chop/regime filters; they trade every valid signal regardless of market structure. Suspected leak: whipsaw losses during consolidations. **Solution:** gate entries (and/or suppress SuperTrend flips) on a composite regime test.

---

### 2.2 Proposed Regime Filter Ruleset (Candidate Parameters)

#### **Filter A: ADX-Based (Simple, Lagging, But Well-Known)**

```
IF ADX(14) < 20:
    SUPPRESS_ENTRIES = True
    # Weak trend; do not open new positions
ELIF ADX(14) >= 20 AND ADX(14) < 30:
    ALLOW_ENTRIES = True  (with caution; moderate trend)
ELIF ADX(14) >= 30:
    ALLOW_ENTRIES = True  (strong trend; full signal processing)
```

**Sweep parameters for backtest:**
- ADX period: {14, 21, 28}
- Lower threshold (suppress below): {15, 20, 25}
- Upper threshold (full enable above): {25, 30, 35}

**Justification:** Wilder (1978) original; practitioner standard. Lagging, but reduces whipsaw in weak-trend periods.

**Source:** Wilder (1978); evidence strength = heuristic.

---

#### **Filter B: Variance Ratio-Based (Rigorous, Requires Calculation)**

```
COMPUTE: VR(q=5, window=100 bars)
IF VR < 0.95:
    REGIME = "mean-reverting"; SUPPRESS_ENTRIES
ELIF 0.95 <= VR <= 1.05:
    REGIME = "choppy"; ALLOW_ENTRIES_WITH_CAUTION (tighter SL)
ELIF VR > 1.05:
    REGIME = "trending"; FULL_ENTRIES
```

**Sweep parameters:**
- Lag q: {3, 5, 7, 10}
- Lookback window: {60, 100, 150, 200 bars}
- Threshold lower: {0.90, 0.95, 1.00}
- Threshold upper: {1.05, 1.10, 1.15}

**Justification:** Lo & MacKinlay (1988); rigorous peer-reviewed foundation. Variance Ratio directly measures serial correlation; VR > 1.05 is statistically significant trend signal (at large N; confidence decreases for small rolling windows).

**Source:** Lo & MacKinlay (1988); Cheung & Lai (1995); evidence strength = rigorous, peer-reviewed.

**Implementation note:** Requires computing sum of squared returns and range statistics. Computationally cheap; suitable for real-time gating.

---

#### **Filter C: Efficiency Ratio-Based (Kaufman; Heuristic)**

```
COMPUTE: ER(N=20 bars) = |close[t] - close[t-N]| / sum(|close[t] - close[t-1]|, t-N to t)
IF ER < 0.40:
    REGIME = "choppy"; SUPPRESS_ENTRIES
ELIF 0.40 <= ER <= 0.60:
    ALLOW_ENTRIES (moderate efficiency)
ELIF ER > 0.60:
    REGIME = "trending"; FULL_ENTRIES
```

**Sweep parameters:**
- ER period N: {10, 15, 20, 30}
- Lower threshold (suppress): {0.30, 0.40, 0.50}
- Upper threshold (full enable): {0.50, 0.60, 0.70}

**Justification:** Kaufman (1995, 2020); directly measures price efficiency (directional progress per unit of volatility). Intuitive. Not peer-reviewed rigorously, but methodical practitioner work.

**Source:** Kaufman (1995+); evidence strength = semi-reliable heuristic.

---

#### **Filter D: Choppiness Index-Based (Practitioner Folklore)**

```
COMPUTE: CI(N=14 bars) = 100 * log₁₀(sum(TR, N bars) / (N-high - N-low)) / log₁₀(N)
IF CI < 38.2:
    REGIME = "trending"; FULL_ENTRIES
ELIF 38.2 <= CI <= 61.8:
    REGIME = "choppy"; SUPPRESS_OR_TIGHTEN_SL
ELIF CI > 61.8:
    REGIME = "extreme chop/reversal"; SUPPRESS_ENTRIES or FLATTEN_POSITION
```

**Sweep parameters:**
- CI period N: {10, 14, 20, 30}
- Chop lower threshold: {35, 38.2, 40}
- Chop upper threshold: {60, 61.8, 65}

**Justification:** Practitioner indicator; no rigorous empirical backing, but intuitive (measures realized chop). Thresholds 38.2 / 61.8 are heuristic (golden ratio folklore; not statistically justified).

**Source:** Hutson (practitioner, early 2010s); evidence strength = practitioner folklore, unverified.

---

### 2.3 HMM Regime-Switching (Advanced)

```
TRAIN: HMM with 3 states on historical {return, volatility (GARCH), ADX} triplets.
  States: "Trending" (low vol + high ADX), "Choppy" (high vol + low ADX), "Regime-Switch" (volatile ADX swings)

ON EACH BAR:
  1. Compute observation (return, garch-vol, ADX)
  2. Filter HMM: infer P(state=Trending | data_so_far)
  3. Gate: IF P(Trending) > 0.7, allow entries; ELSE suppress
```

**Justification:** Hamilton (1989); Guidolin & Timmermann (2007). Theoretically sound, empirically validated. More computation than simpler filters, but captures regime dynamics.

**Source:** Hamilton (1989), Guidolin & Timmermann (2007); evidence strength = rigorous, peer-reviewed.

---

### 2.4 Composite Filter (Recommended Approach)

Rather than relying on a single indicator, combine multiple weak signals into a decision rule:

```
SCORE = 0
IF ADX(14) > 25: SCORE += 1
IF VR(5, 100 bars) > 1.05: SCORE += 1
IF ER(20) > 0.50: SCORE += 1
IF CI(14) < 42: SCORE += 1

IF SCORE >= 3:  # At least 3 of 4 agree on trending
    ALLOW_ENTRIES = True
ELSE:
    SUPPRESS_ENTRIES = True
```

**Rationale:** No single indicator is perfect. Combining reduces false signals. Composite thresholds can be swept in backtest.

---

## 3. Evidence-Backed vs Folklore: Separation and Recommendations

### 3.1 Strong Empirical/Theoretical Backing

| Method | Source(s) | Evidence Type | Recommendation |
|--------|-----------|---------------|-----------------|
| **Variance Ratio Test** | Lo & MacKinlay (1988); Cheung & Lai (1995) | Rigorous peer-reviewed; statistical foundation | **Use as primary filter.** Requires careful implementation of rolling window stats. |
| **HMM Regime-Switching** | Hamilton (1989); Guidolin & Timmermann (2007) | Rigorous peer-reviewed; proven empirical gains | **Use if computational resources available.** Moderate complexity; strong theoretical backing. |
| **GARCH Volatility Regime** | Engle (1982); widespread in finance | Peer-reviewed, well-established | **Use as secondary regime marker.** Detect vol clustering correlated with chop. |

---

### 3.2 Semi-Reliable Heuristics (Practitioner-Developed, Limited Rigorous Validation)

| Method | Source(s) | Evidence Type | Recommendation |
|--------|-----------|---------------|-----------------|
| **Kaufman's Efficiency Ratio** | Kaufman (1995+) | Methodical; example-based, not peer-reviewed | **Use cautiously.** Threshold (0.40/0.60) is heuristic; should be swept in backtest. Works in practice but lacks rigorous empirical validation. |
| **ADX** | Wilder (1978) | Heuristic; practitioner consensus | **Use as secondary/supplementary filter only.** Lagging, arbitrary thresholds (ADX > 25). Do NOT rely solely. Many empirical studies show poor stand-alone performance. |
| **Bid-Ask Spread / Volume** | Goodhart & O'Hara (1997); market microstructure | Indirect observation; limited direct evidence for trading regime | **Use as supplementary filter only.** Note: XAUUSD spread bimodal 0.50/0.60; wider spread (0.60) may indicate lower liquidity; gate conservatively when spread widens. |

---

### 3.3 Folklore / Unverified (Do Not Rely On)

| Method | Source(s) | Evidence Type | Recommendation |
|--------|-----------|---------------|-----------------|
| **Choppiness Index** | Hutson (practitioner, 2010s); unverified origin | Practitioner heuristic; no peer-reviewed validation | **Avoid as primary filter.** Elegant formula but thresholds (38.2/61.8) are arbitrary and not statistically justified. Can use for supplementary signals (e.g., alert if CI > 65), but do not gate critical entries on CI alone. |
| **Hurst Exponent (R/S Analysis)** | Peters (1991); criticized by Lo (1991) | Theoretically motivated, but empirically controversial; known bias issues | **Avoid.** R/S analysis is biased for finite samples. Peters' original claims are disputed. Unless using bias-corrected estimators (Anis & Lloyd detrending), estimates are unreliable. **Not recommended for real-time trading.** |

---

## 4. Specific Recommendations for S6-K2P0 and SuperTrend-p14x3-M15

### 4.1 S6-K2P0 (Multiple Entry Signals, Stop & Reverse)

**Current weakness:** Enters on every gate-pass regardless of regime. Suspected whipsaw during ranging markets because SL is ATR-based (can be very tight in low-vol chop).

**Proposed regime filter:** Add gate between entry signal detection and position open.

```
ENTRY_SIGNAL_DETECTED:
  IF REGIME_FILTER_SCORE >= 3:  # (or HMM P(Trending) > 0.7)
      OPEN_POSITION as normal
  ELSE:
      SKIP_ENTRY (do not open)

IF POSITION_OPEN and OPPOSITE_SIGNAL:
  # Current: force close and reverse
  # Proposed: also check regime
  IF REGIME_FILTER_SCORE >= 3:
      REVERSE as normal
  ELSE:
      HOLD_POSITION (do not flip unless signal is strong)
```

**Backtest sweep:**
- Regime filter type: {ADX-only, VR-only, ER-only, Composite-3of4, HMM}
- Corresponding thresholds (per section 2.2)
- Measure impact on: net PnL, max drawdown, win rate, avg loss per trade

**Expected outcome:** Fewer whipsaw-driven losses during consolidation phases; slight reduction in trade count (acceptable if PnL improves).

---

### 4.2 SuperTrend-p14x3-M15 (Always-In Engine, Sensitive to Chop)

**Current weakness:** "Always-in" design forces continuous directional exposure. In ranging market, flips constantly on noise; each flip crystallizes a loss near ATR*3 ≈ $3−6 per flip (depending on volatility).

**Proposed regime filter:** Modify entry/flip rules to pause during choppy regimes.

```
ON EACH NEW CLOSED BAR:
  COMPUTE: SuperTrend line (ATR 14, mult 3.0)
  COMPUTE: Regime score (as per section 2.2)
  
  IF REGIME_SCORE < 2:  # Choppy regime (less than 2 of 4 indicators agree on trending)
      IF NO_POSITION:
          WAIT (do not open)
      ELIF POSITION_OPEN and TREND_LINE_CROSSED:
          HOLD (do not flip; wait for stronger signal)
  ELSE:  # Trending regime (2+ of 4 agree)
      IF TREND_LINE_CROSSED:
          FLIP_POSITION (as normal)
```

**Backtest sweep:**
- Regime filter type: {VR (most rigorous), ER, Composite}
- Score threshold to suppress flips: {1, 2}
- Measure impact on: net PnL, max drawdown, slippage-driven loss%, ratio of whipsaw-losses to valid trend gains

**Expected outcome:** Reduce small-loss-generating flips during chop; accept holding longer through regime-switch consolidations (may miss some flip-back wins, but net PnL should improve if whipsaws > missed gains).

---

## 5. Action Items for Backtest Implementation

1. **Data preparation:** Ensure XAUUSD M15 bars have clean close, high, low, volume. Compute true-range (TR).

2. **Indicator library:** Implement:
   - ADX(period)
   - Variance Ratio (rolling VR with lag q, window size)
   - Efficiency Ratio (ER)
   - Choppiness Index (CI)
   - (Optional: GARCH volatility, HMM)

3. **Filter integration:** Wrap entry logic in regime check; gate S6-K2P0 entries and SuperTrend flips on regime score.

4. **Sweep grid:** Test combinations:
   - **VR-based:** q ∈ {3, 5, 7}, window ∈ {60, 100, 150}, threshold ∈ {0.90, 0.95, 1.05, 1.10}
   - **ADX-based:** period ∈ {14, 21}, lower ∈ {15, 20, 25}, upper ∈ {25, 30, 35}
   - **ER-based:** N ∈ {10, 20, 30}, lower ∈ {0.30, 0.40, 0.50}, upper ∈ {0.50, 0.60, 0.70}
   - **Composite:** vary score threshold ∈ {2, 3}

5. **Validation:**
   - Out-of-sample test on held-out date range.
   - Measure regime filter accuracy: when filter predicts "choppy," is ADX actually low? Is realized volatility high? (Sanity check.)
   - Measure PnL impact separately: filter's reduction in entries, reduction in whipsaw losses, any reduction in valid-trend capture.

6. **Documentation:** Log regime filter decision on each bar (entry suppressed? why?), so post-backtest analysis can explain which filter prevented which losses/gains.

---

## 6. Summary Table: Sources, Evidence Strength, Recommendations

| Method | Key Reference(s) | Evidence Strength | Applicability to XAUUSD M15 | Recommendation |
|--------|------------------|-------------------|---------------------------|-----------------|
| Variance Ratio | Lo & MacKinlay (1988) | **Rigorous; peer-reviewed** | High | **Primary filter candidate** |
| HMM Regime-Switching | Hamilton (1989) | **Rigorous; peer-reviewed** | High (if implemented correctly) | **Excellent alternative if resources allow** |
| Kaufman's ER | Kaufman (1995+) | Semi-reliable; practitioner | Moderate | **Secondary filter; sweep thresholds** |
| ADX | Wilder (1978) | Heuristic; weak empirical backing | Moderate (lagging) | **Not primary; use with caution** |
| Choppiness Index | Hutson (practitioner) | **Unverified; folklore** | Low (heuristic only) | **Avoid as primary; supplementary only** |
| GARCH Volatility | Engle (1982) | Rigorous; peer-reviewed | Moderate | **Secondary regime marker** |
| Hurst Exponent (R/S) | Peters (1991); criticized Lo (1991) | **Controversial; bias issues** | Low; not recommended | **Avoid for real-time trading** |
| Bid-Ask Spread / Volume | Goodhart & O'Hara (1997) | Indirect observation | Low for XAUUSD (instrument specific) | **Supplementary only; note bimodal spread** |

---

## 7. Caveats and Open Questions

1. **Regime definitions are not universal.** A regime that works for EURUSD may differ from XAUUSD; backtest required to validate filter parameters on this instrument.

2. **Lagging vs. leading.** All indicators discussed are lagging (react to past price) or concurrent; none are truly predictive. VR and ER have lower lag than ADX, but still react post-event. HMM can infer state probabilities in real-time but requires historical training.

3. **Parameter sensitivity.** Filter thresholds (ADX > 25, VR > 1.05, ER > 0.50) are not set in stone. Backtest grid sweep is mandatory; no universal threshold exists.

4. **Small sample bias.** For rolling windows (e.g., 100 M15 bars ≈ 25 hours of trading), VR estimates have high variance. Composite filter (combining 3−4 indicators) reduces variance of regime decision.

5. **Market regime non-stationarity.** XAUUSD regimes may shift over time (e.g., correlation with equities changes, fed policy changes); periodically retrain/revalidate filter on recent data.

6. **SuperTrend's always-in constraint.** Suppressing entries in choppy regime is natural for S6-K2P0. For SuperTrend, "always-in" is core design; suppressing flips might violate intended strategy. Alternative: allow flips, but tighten SL when choppy (reduce per-flip loss). Requires separate backtest.

---

## References

Anis, A.A. & Lloyd, E.H. (1976). The expected value of the adjusted rescaled Hurst range of independent normal summands. *Biometrika*, 63(1), 111−116.

Cheung, Y.-W. & Lai, K.S. (1995). A search for long memory in international stock market returns. *Journal of International Money and Finance*, 14(4), 597−615.

Engle, R.F. (1982). Autoregressive conditional heteroskedasticity with estimates of the variance of United Kingdom inflation. *Econometrica*, 50(4), 987−1007.

Goodhart, C.A.E. & O'Hara, M. (1997). High frequency data in financial markets: Issues and applications. *Journal of Empirical Finance*, 4(2−3), 73−114.

Guidolin, M. & Timmermann, A. (2007). Asset allocation under multivariate regime switching. *Journal of Economic Dynamics and Control*, 31(11), 3503−3544.

Hamilton, J.D. (1989). A new approach to the economic analysis of nonstationary time series and the business cycle. *Econometrica*, 57(2), 357−384.

Hurst, H.E. (1951). Long-term storage capacity of reservoirs. *Transactions of the American Society of Civil Engineers*, 116(1), 770−799.

Kaufman, P.J. (1995, 2020). *New Trading Systems and Methods* (2nd–5th editions). Hoboken, NJ: Wiley.

Lo, A.W. (1991). Long-term memory in stock market prices. *Journal of Econometrics*, 46(1−2), 99−120.

Lo, A.W. & MacKinlay, A.C. (1988). Stock market prices do not follow random walks: Evidence from a simple specification test. *Journal of Financial Economics*, 41(1), 3−26.

Peters, E.E. (1991). *Chaos and Order in the Capital Markets: A New View of Cycles, Prices, and Market Volatility*. Hoboken, NJ: Wiley.

Wilder, J.W. (1978). *New Concepts in Technical Trading Systems*. McLeanville, TN: Trend Research.

---

*End of literature review (Area 2: Regime Detection and Ranging/Sideways Markets).*
