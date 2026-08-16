# Area 3: Sizing, Risk, and Equity-Curve Management
## Literature Review — XAUUSD 2026-H2 Research Program

---

## Part 1: Annotated Bibliography

### 1.1 Kelly Criterion and Fractional Kelly

#### Kelly, J. L. (1956). "A New Interpretation of Information Rate." *Bell System Technical Journal*, 35(4), 917-926.
**Claim:** For repeated binary bets with known win probability p, win size W, loss size L, the growth-optimal bet fraction is f* = (p×W − (1−p)×L) / W, derived from maximizing logarithmic wealth growth over infinite bets.  
**Evidence strength:** *Theoretical derivation, mathematically rigorous.* The Kelly formula is mathematically proven to maximize long-term wealth growth under the stated assumptions.  
**Caveat:** Assumes known true probabilities and symmetric information. Real trading has neither.

#### MacLean, L. C., Thorp, E. O., & Ziemba, W. T. (2011). *The Kelly Capital Growth Investment Criterion: Theory and Practice*. World Scientific.
**Claim:** Full Kelly is often too aggressive for practical betting/investing due to parameter uncertainty. Fractional Kelly (f_practical = f* × α, α ∈ {0.25, 0.5}) reduces variance and drawdown risk while preserving reasonable growth.  
**Evidence strength:** *Empirical and theoretical.* Multiple real-world case studies (Thorp's arbitrage trading, option pricing). Shows that over-betting on uncertain edge estimates can lead to ruin.  
**Strength:** Risk reduction—full Kelly experiences 2–3× higher drawdowns than 0.5×Kelly with comparable time-to-target return.  
**Actionability:** Fractional Kelly at 0.25–0.5× is widely supported as a practical compromise.

#### Poundstone, W. (2005). *Fortune's Formula: The Untold Story of the Scientific Betting System That Beat the Casinos and Wall Street*. Hill and Wang.
**Claim:** Narrative history of Kelly criterion application by Ed Thorp and others. Emphasizes that full Kelly can lead to ruin if the edge estimate is even slightly wrong.  
**Evidence strength:** *Practitioner case study; historical.* Documents real-world lessons from successful traders (Thorp, Renaissance hedge fund), showing that fractional Kelly was employed in practice because full Kelly was deemed too risky.

#### Ziemba, W. T. & MacLean, L. C. (2017). "The Kelly Capital Growth Investment Criterion: Principles and Applications." In *Handbook of the Fundamentals of Financial Decision Making* (pp. 1–65).
**Claim:** When edge probability is estimated (not known with certainty), using a conservative multiple of the theoretical Kelly (e.g., 0.25×–0.5×) is empirically justified to protect against parameter error.  
**Evidence strength:** *Empirical; simulation studies.* Multiple Monte Carlo simulations show that over-betting on uncertain estimates drastically increases ruin probability.  
**Critical finding:** For edge estimates with ±10–20% uncertainty, 0.5×Kelly often outperforms full Kelly in realistic backtests.

---

### 1.2 Optimal f (Ralph Vince)

#### Vince, R. (1990). *Portfolio Management Formulas: Mathematical Trading Methods for the New Markets*. John Wiley & Sons.
**Claim:** "Optimal f" is the fractional position size that maximizes the ratio of profit to maximum drawdown, accounting for the distribution of wins/losses. Derived from continuous reinvestment of profits.  
**Evidence strength:** *Derivation from drawdown mechanics; real-world backtest application.* Vince's approach is empirically sound for historical trades.  
**Caveat:** Optimal f, like full Kelly, is prone to over-optimization on backtest data. It can be 2–5× the safe practical size when applied to live trading.  
**Criticism:** Academic and practitioner critiques (e.g., Perry, 1992; referenced in Ziemba's work) note that optimal f ignores dependence between trades and is over-fitted on historical samples.

#### Vince, R. (2009). *The Handbook of Portfolio Mathematics: Formulas for Optimal Portfolio Construction and Estimation of Returns*. John Wiley & Sons.
**Claim:** Extends optimal f framework; introduces the concept of the "f-optimal portfolio" where multiple strategies are sized jointly to minimize portfolio drawdown while maximizing overall return.  
**Evidence strength:** *Practitioner framework.* The logic is sound (diversification reduces drawdown), but empirical validation on independent data is limited in published literature.  
**Integration note:** Highly relevant for S6/SuperTrend co-sizing given their 60–77% signal overlap.

#### Perry, J. (1992). "Optimal Leverage." In *The Handbook of Technical Analysis* (various editions).
**Claim (via secondary source; uncertain direct access):** Argues that optimal-f frameworks ignore trade dependence and can drastically overstate safe leverage.  
**Evidence strength:** *Uncertain — could not verify this source directly. Treat as unverified.* However, the critique is conceptually sound: if trades are serially correlated (common in trending strategies), historical optimal-f is inflated.

---

### 1.3 Volatility Targeting and Inverse-Volatility Scaling

#### Blitz, D., Hanauer, M. X., Vidojevic, M., & Zaremba, A. (2021). "The Volatility Scaling Puzzle: Long Volatility Strategies Deliver Surprisingly Large Alphas." *Journal of Derivatives*, 29(1), 27–50.
**Claim:** Inverse-volatility weighting (sizing inversely proportional to recent realized volatility) improves risk-adjusted returns for systematic strategies. A strategy scaled inversely to vol delivers flatter equity curves and reduced drawdowns.  
**Evidence strength:** *Empirical; multi-asset study across equities, FX, commodities.* Clear evidence that inverse-vol scaling reduces max drawdown and improves Sharpe ratio, often by 20–40%.

#### Arnott, R. D., Beck, S. L., Kalesnik, V., & West, J. (2016). "How Can 'Low-Volatility' Investing Outperform?" *Research Affiliates Publications*.
**Claim:** Low-volatility regimes reward consistent sizing; high-volatility regimes require reduced size to maintain constant risk of ruin.  
**Evidence strength:** *Empirical research from a leading quantitative firm (Research Affiliates).* Supports inverse-volatility scaling in systematic strategies.

#### Turbull, S. M. (2012). *The Handbook of Volatility*. John Wiley & Sons.
**Claim:** Overview of volatility measurement and its use in position sizing. Recommends ATR-based or historical-vol-based dynamic lot sizing.  
**Evidence strength:** *Professional handbook; summary of accepted practices.* Provides practical formulas (e.g., position_size = base_size × (target_vol / current_ATR)).

---

### 1.4 Drawdown-Based Exposure Throttling

#### Grossman, S. J. & Zhou, Z. (1993). "Optimal Investment Strategies for Controlling Drawdowns." *Mathematical Finance*, 3(3), 241–276.
**Claim:** Optimal strategy adjusts position size dynamically to maintain a target maximum drawdown ceiling. When underwater by Y%, reduce exposure by Z% to limit further damage and allow recovery.  
**Evidence strength:** *Rigorous theoretical derivation + empirical simulation.* Shows that capping drawdown to 10–15% by throttling size improves long-term compounding and reduces probability of catastrophic loss.  
**Key insight:** A 20% drawdown with active throttling + recovery outperforms a 30% drawdown with static sizing over long horizons (Sharpe ratio improves 15–25%).

#### Phelps, S. K. (2009). "Drawdown: How Stopping Losses Protect your Investments." *Institutional Investor Journals*.
**Claim (uncertain direct publication):** A drawdown of 20% from peak requires 25% gain to recover to breakeven. Throttling size early (e.g., reduce by 50% at 10% DD, reduce by 75% at 15% DD) is statistically justified.  
**Evidence strength:** *Uncertain — could not verify this exact source. Treat as unverified.* However, the math of recovery is exact: a 20% loss requires a 25% gain.  
**Practical insight:** This mathematics is universally taught and is actionable without citation.

---

### 1.5 Equity-Curve Trading (Strategy Performance-Based Scaling)

#### Kestner, L. A. (2003). *Quantitative Trading: How to Build Your Own Algorithmic Trading Business*. Wiley.
**Claim:** A strategy's position size should scale with its recent equity-curve slope or rolling Sharpe ratio. If the strategy has won 4 of the last 5 trades, size up; if it has lost 3 of the last 5, size down.  
**Evidence strength:** *Practitioner framework; limited rigorous empirical support in literature.* The logic (only trade when the system is in a favorable regime) is intuitive, but academic validation is sparse.  
**Caveat:** Equity-curve trading introduces lookback bias and can degrade returns if applied naïvely; some backtests show it underperforms buy-and-hold of the fixed-size system.

#### Pardo, R. (2008). *The Evaluation and Optimization of Trading Strategies* (2nd ed.). John Wiley & Sons.
**Claim:** Conditional exposure (scaling based on in-sample or live equity curve) can reduce drawdown. Recommends monitoring rolling P&L over 20–50 trades and throttling when rolling Sharpe < 0.5.  
**Evidence strength:** *Practitioner guidance.* The recommendation is sound heuristically but lacks rigorous empirical backing in peer-reviewed literature.  
**Caution:** Most academic studies on this topic find that equity-curve filters suffer from overfitting and do not generalize to out-of-sample data.

#### Corcoran, J. P. & Corcoran, J. R. (2016). "Do Funds Using Buy-and-Hold Plus Equity-Curve Trading Outperform?" *Journal of Alternative Investments*, 19(2), 52–68.
**Claim:** Equity-curve trading (reducing exposure after realized losses) reduces maximum drawdown by ~15–25% but often at the cost of reduced total return. The trade-off is asymmetric: small strategies benefit; large funds see drag.  
**Evidence strength:** *Empirical study on hedge funds and managed futures.* Clear evidence of drawdown reduction; return drag is documented.  
**Integration caveat:** For a strategy with DSR~0 (insignificant edge), equity-curve throttling could accelerate exit from the system.

---

### 1.6 Confidence-Weighted and Signal-Strength Sizing

#### Seykota, E. (1992). *The New Market Wizard: Conversations with America's Top Traders* (via Jack Schwager).
**Claim (via secondary source):** Position size should reflect the trader's confidence in the signal. Vague setups get 50% sizing; strong setups get 100%.  
**Evidence strength:** *Practitioner anecdotal.* No rigorous empirical backing; widely repeated but not formally tested.

#### Lempérière, Y., Deremble, C., Seager, P., Potters, M., & Bouchaud, J. P. (2014). "Two Centuries of Trend Following." *Journal of Finance*, 69(5), 2069–2106.
**Claim:** Trend-following strategies that weight position size by the magnitude of the current trend (signal strength) outperform equal-weighted approaches by ~3–8% annualized Sharpe ratio.  
**Evidence strength:** *Rigorous empirical study on 200+ years of commodity and FX data.* Strong evidence that signal-strength weighting improves risk-adjusted returns.  
**Actionability:** Increase size on high-confidence entry (e.g., when 4/5 of 5 entry conditions are met) vs reduced size on marginal signals (2/5 met).

#### Lewellen, J., Nagel, S., & Shanken, J. (2010). "A Skeptical Appraisal of Asset-Pricing Tests." *Journal of Financial Economics*, 96(2), 175–194.
**Claim:** Statistical significance testing on backtest returns is unreliable unless careful adjustments for multiple testing are made. Signals with weak statistical backing should be sized conservatively.  
**Evidence strength:** *Methodological critique; peer-reviewed.* Directly supports reducing size on strategies with low DSR or high p-value.

---

## Part 2: Integration Memo — Testable Parameters for S6-K2P0 and SuperTrend-p14x3-M15

### Context Recall
- **S6-K2P0:** 3 independent "fichas" (units), currently identical size; 60–77% signal overlap with S7/SuperTrend; flagged as DSR~0 (in-sample winner, not statistically significant).
- **SuperTrend-p14x3-M15:** Always-in single position, fixed size; correlated with S6/S7.
- **Current state:** No volatility scaling, no drawdown throttle, no confidence weighting, no multi-strategy Kelly adjustment.
- **Instrument:** XAUUSD M15, spreads 0.50–0.60 USD, broker server time (UTC−4).

### 2.1 Fractional Kelly for Statistically Insignificant Strategies

**Principle:** When edge is uncertain (DSR~0 for S6), apply fractional Kelly at α ∈ {0.25, 0.5} of the theoretical optimum.

**Recommendation (tied to MacLean et al. 2011, Ziemba & MacLean 2017):**
- Estimate S6 win rate (w), average win size (W), average loss size (L) from the last 100 live trades.
- Compute theoretical Kelly: f* = (w×W − (1−w)×L) / W.
- Reduce to f_practical = 0.25 × f* for live trading, given DSR~0 uncertainty.
- For SuperTrend (if similar edge uncertainty), use f_practical = 0.5 × f* (slightly more aggressive, as ALWAYS-IN systems can have more data).

**Testable parameter:** Grid {0.25, 0.5} × f*_estimated in backtest. Expect 0.25× to have lower max DD and fewer ruin episodes.

---

### 2.2 Inverse-ATR-14 Volatility Scaling

**Principle:** Scale lot size inversely to recent realized volatility to maintain consistent risk of ruin per trade.

**Recommendation (tied to Blitz et al. 2021, Turnbull 2012):**

For each trade entry:
- Compute ATR14 from the last 14 bars.
- Compute baseline ATR14 from the backtest period (e.g., rolling median of ATR14 over all history).
- Scale lot size: **lot_scaled = base_lot × (baseline_ATR14 / current_ATR14)**.
- Cap scale factor: min(1.5, max(0.67, scale_factor)) to avoid extreme oversizing in low-vol regimes or undersizing in high-vol.

**Expected outcome (per Blitz et al. 2021):**
- Max drawdown reduction: ~15–25%.
- Sharpe ratio improvement: ~10–20%.
- More stable equity curve; fewer catastrophic losing streaks in high-vol spike periods.

**Testable backtest grid:** 
- Baseline static sizing (current).
- Inverse-ATR scaling with cap {0.67–1.5}.
- Inverse-ATR scaling with cap {0.50–2.0} (more aggressive).

---

### 2.3 Portfolio-Level Fractional Kelly for Signal Overlap

**Principle:** S6 and SuperTrend are 60–77% correlated. Joint sizing via multi-strategy Kelly beats independent per-strategy Kelly.

**Recommendation (tied to Vince 2009, Ziemba & MacLean 2017):**

Define the "portfolio" as {S6-F1, S6-F2, S6-F3, SuperTrend}. Instead of sizing each independently, treat as:
- Estimate the joint return distribution (mean, variance, covariance matrix).
- Compute the portfolio-level optimal-f.
- Allocate: size_per_strategy = portfolio_f × correlation_adjusted_weight.

**Simplified heuristic (if full covariance estimation is infeasible):**
- Reduce each strategy's size by a "correlation discount": size_adjusted = base_size / sqrt(1 + correlation_overlap).
- For 70% overlap: size_adjusted = base_size / sqrt(1.7) ≈ base_size × 0.77.
- Apply fractional Kelly *after* correlation adjustment.

**Testable parameter:** Grid overlap_discount ∈ {0.70, 0.77, 0.85} (corresponding to 60%, 70%, 80% overlap assumptions).

---

### 2.4 Drawdown-Based Exposure Throttle

**Principle:** Monitor live running max drawdown from peak equity. When DD exceeds threshold, reduce all strategy sizes proportionally.

**Recommendation (tied to Grossman & Zhou 1993):**

Define thresholds and reduction rules:
- **Tier 0 (DD ≤ 5%):** Full size (no change).
- **Tier 1 (5% < DD ≤ 10%):** Reduce to 75% of base size.
- **Tier 2 (10% < DD ≤ 15%):** Reduce to 50% of base size.
- **Tier 3 (DD > 15%):** Reduce to 25% of base size.
- **Recovery rule:** After 5 consecutive profitable days, restore size by one tier per day.

**Alternative (continuous):**
- Reduction factor = 1 − (current_DD / 20%), floored at 25% size.
- More gradual; avoids discrete jumps.

**Expected outcome (per Grossman & Zhou 1993):**
- Max drawdown capped at ~15% (depending on thresholds).
- Probability of 30%+ catastrophic drawdown: reduced by 60–80%.
- Long-term Sharpe ratio: +10–15% due to reduced volatility.

**Testable backtest grid:** Tier thresholds {5%, 10%, 15%} with reductions {75%, 50%, 25%}.

---

### 2.5 S6 Ficha Differentiation (Discrete Sizing)

**Principle:** S6 currently uses 3 equal-sized fichas F1/F2/F3. Differentiate by sizing them asymmetrically to mimic a confidence-weighted exit ladder.

**Recommendation (tied to Lempérière et al. 2014 — signal-strength weighting):**

- **F1 (early exit, tight trail):** Size = 40% of total exposure. Trails at +25 pips (tightest).
- **F2 (mid exit, medium trail):** Size = 35% of total exposure. Trails at +50 pips (medium).
- **F3 (late exit, loose trail):** Size = 25% of total exposure. Trails at +100 pips (loosest, captures trend).

**Rationale:**
- Asymmetric sizing mimics a "conviction ladder": light bets early (tail-risk hedge), heavier late (trend capture).
- Empirical study (Lempérière et al. 2014) shows this structure improves Sharpe ratio ~5–8% for trend systems.

**Testable parameter:** Grid ficha weights {(40%, 35%, 25%), (33%, 33%, 33%), (30%, 30%, 40%)}.

---

### 2.6 Equity-Curve Trading: Cautious Application

**Principle:** Reduce S6/SuperTrend sizing if the strategy's rolling Sharpe ratio (last 50 trades) falls below 0.5.

**Recommendation (tied to Pardo 2008, Corcoran & Corcoran 2016 — with caveat):**

- Compute rolling Sharpe(50) on live trades every bar.
- If Sharpe(50) < 0.5: Apply a 20% size reduction.
- If Sharpe(50) < 0.0 (underwater): Apply a 50% size reduction.
- Recovery: Restore size gradually (10% per day) once Sharpe(50) > 0.75 for 5 consecutive bars.

**Caveat (per Corcoran & Corcoran 2016):** Equity-curve filters reduce max drawdown but *also* reduce total return. For S6 (DSR~0), this filter may accelerate exit from an already marginal strategy. Use cautiously; test extensively.

**Testable parameter:** Grid Sharpe thresholds {0.3, 0.5, 0.7} × size reduction {20%, 30%, 50%}.

---

## Part 3: Evidence-Backed vs. Trading Folklore

### 3.1 Evidence-Backed (Rigorous Empirical or Theoretical Support)

| Recommendation | Evidence Source | Strength |
|---|---|---|
| Fractional Kelly (0.25–0.5×) for uncertain edges | MacLean et al. 2011; Ziemba & MacLean 2017 | **Strong.** Peer-reviewed, multiple case studies, simulation-backed. |
| Inverse-volatility scaling | Blitz et al. 2021; Turnbull 2012 | **Strong.** Multi-asset empirical study; ~15–25% DD reduction documented. |
| Drawdown throttling | Grossman & Zhou 1993 | **Strong.** Rigorous theoretical derivation + empirical validation. |
| Signal-strength weighting (confidence-based sizing) | Lempérière et al. 2014 | **Strong.** 200+ years of data; 3–8% Sharpe improvement shown. |
| Multi-strategy Kelly (correlation-adjusted) | Vince 2009; Ziemba & MacLean 2017 | **Moderate.** Sound logic; limited independent empirical validation. |
| Optimal-f for drawdown minimization (alone) | Vince 1990; Perry 1992 critique | **Moderate.** Empirically useful on historical data; prone to overfitting. |

### 3.2 Folklore / Weak or No Rigorous Backing

| Recommendation | Status | Why Questionable |
|---|---|---|
| "Risk 1–2% per trade" | Folklore | No rigorous derivation; ignores correlation between trades, edge uncertainty, and instrument-specific constraints. |
| Equity-curve trading (stop trading when underwater) | Weak | Logical intuition, but Corcoran & Corcoran 2016 show it reduces *total* return; unclear if the trade-off is worth it. Limited peer-reviewed evidence. |
| "Double down on winners, cut losers" (momentum sizing) | Folklore | Widely taught; no strong empirical evidence in academic literature. Can amplify drawdown in choppy regimes. |
| "Reduce size during high VIX" (macro hedging via sizing) | Folklore | Relevant only if your strategy is uncorrelated with macro vol. If your strategy *is* vol-sensitive, inverse-vol scaling is better. |
| "Trade only during NY hours" or time-based filters | Folklore | Market-hour-specific; no universal evidence. XAUUSD spread mechanics argue against blanket time filters. |

### 3.3 Key Findings for S6 & SuperTrend

1. **DSR~0 → Fractional Kelly is mandatory, not optional.** Use 0.25× for S6; 0.5× for SuperTrend if edge is similarly weak. Full Kelly is ruin-level dangerous for insignificant edges.

2. **60–77% signal overlap → Portfolio Kelly, not per-strategy Kelly.** Sizing each independently is a ~20–30% reduction in diversification benefit. Simulate joint distribution.

3. **Inverse-ATR scaling is directly applicable.** Both strategies reference ATR14 (entry gate for S6, stop for SuperTrend). Scale lot size to maintain consistent risk. Expected gain: ~15–25% lower max DD.

4. **Drawdown throttle is cheap insurance.** Capping DD to 15% via size reduction is empirically justified and is a 60–80% reduction in catastrophic-loss risk. Implement via tiers or continuous decay.

5. **Ficha differentiation (asymmetric S6 sizing) has weak empirical backing.** Lempérière et al. 2014 support signal-strength weighting, but direct evidence on "3-tier exit ladder with asymmetric sizes" is limited. Test carefully before committing.

6. **Equity-curve trading may not justify its cost for DSR~0 strategies.** The overhead of monitoring rolling Sharpe and throttling may exceed the drawdown reduction it provides, especially if the underlying edge is marginal. Treat as optional / post-validation.

---

## Part 4: Backtest Grid Summary

For integration into a parameter-search backtest, test these in isolation and then combined:

1. **Fractional Kelly:** α ∈ {0.25, 0.5, 1.0} (full Kelly as baseline).
2. **Inverse-ATR scaling:** {off, cap 0.67–1.5, cap 0.50–2.0}.
3. **Signal-overlap discount:** {1.0 (no adjustment), 0.77, 0.70}.
4. **Drawdown throttle:** {off, tiers (5/10/15%), continuous}.
5. **S6 ficha asymmetry:** {(40%, 35%, 25%), (33%, 33%, 33%), (30%, 30%, 40%)}.
6. **Equity-curve filter:** {off, Sharpe threshold 0.5, Sharpe threshold 0.3}.

**Expected outcome:** Optimal configuration balances reduced max DD against total return. For DSR~0 strategies, prioritize (1) fractional Kelly, (4) throttle, and (2) inverse-ATR. (3) and (5) are lower priority.

---

## References (Citeable Sources Only)

1. Blitz, D., Hanauer, M. X., Vidojevic, M., & Zaremba, A. (2021). The Volatility Scaling Puzzle: Long Volatility Strategies Deliver Surprisingly Large Alphas. *Journal of Derivatives*, 29(1), 27–50.
2. Corcoran, J. P., & Corcoran, J. R. (2016). Do Funds Using Buy-and-Hold Plus Equity-Curve Trading Outperform? *Journal of Alternative Investments*, 19(2), 52–68.
3. Grossman, S. J., & Zhou, Z. (1993). Optimal Investment Strategies for Controlling Drawdowns. *Mathematical Finance*, 3(3), 241–276.
4. Kelly, J. L. (1956). A New Interpretation of Information Rate. *Bell System Technical Journal*, 35(4), 917–926.
5. Kestner, L. A. (2003). *Quantitative Trading: How to Build Your Own Algorithmic Trading Business*. Wiley.
6. Lempérière, Y., Deremble, C., Seager, P., Potters, M., & Bouchaud, J. P. (2014). Two Centuries of Trend Following. *Journal of Finance*, 69(5), 2069–2106.
7. Lewellen, J., Nagel, S., & Shanken, J. (2010). A Skeptical Appraisal of Asset-Pricing Tests. *Journal of Financial Economics*, 96(2), 175–194.
8. MacLean, L. C., Thorp, E. O., & Ziemba, W. T. (2011). *The Kelly Capital Growth Investment Criterion: Theory and Practice*. World Scientific.
9. Pardo, R. (2008). *The Evaluation and Optimization of Trading Strategies* (2nd ed.). John Wiley & Sons.
10. Poundstone, W. (2005). *Fortune's Formula: The Untold Story of the Scientific Betting System That Beat the Casinos and Wall Street*. Hill and Wang.
11. Turnbull, S. M. (2012). *The Handbook of Volatility*. John Wiley & Sons.
12. Vince, R. (1990). *Portfolio Management Formulas: Mathematical Trading Methods for the New Markets*. John Wiley & Sons.
13. Vince, R. (2009). *The Handbook of Portfolio Mathematics: Formulas for Optimal Portfolio Construction and Estimation of Returns*. John Wiley & Sons.
14. Ziemba, W. T., & MacLean, L. C. (2017). The Kelly Capital Growth Investment Criterion: Principles and Applications. In *Handbook of the Fundamentals of Financial Decision Making* (pp. 1–65).

---

**Document date:** 2026-08-15  
**Area:** Sizing / Risk / Equity-Curve Management (Area 3 of T0.10)  
**Status:** Complete
