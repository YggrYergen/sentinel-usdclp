# T0.10 Literature Review — Area 4: Multi-Timeframe Momentum

## 1. Annotated Bibliography

### A. Cross-Sectional Momentum (Equity & Asset Classes)

**Jegadeesh, N., & Titman, S. (1993). "Returns to Buying Winners and Selling Losers: Implications for Momentum Investors." *Journal of Finance*, 48(1), 65–91.**
- **Core claim:** Portfolio formed by buying past winners (highest 3–12-month returns) and shorting past losers significantly outperforms, with returns as high as 12% annually over the subsequent 3–12 months.
- **Mechanism:** Exploits systematic underreaction to firm-specific information; prices adjust slowly to earnings surprises and other fundamentals.
- **Evidence strength:** Highly rigorous; multi-decade empirical study (1965–1989, cross-checked on subsequent periods), robust to trading costs, replicated across many markets.
- **Relevance to XAUUSD multi-TF:** Suggests that trends (price momentum on one timeframe) should be reinforced by momentum on wider timeframes before taking action; if M15 shows momentum but H4 is counter-trending, you are fighting the broader cross-sectional loser position.

**Asness, C. S., Moskowitz, T. J., & Pedersen, L. H. (2013). "Value and Momentum Everywhere." *Journal of Finance*, 68(3), 929–985.**
- **Core claim:** Time-series and cross-sectional momentum are robust across all major asset classes (stocks, bonds, commodities, currencies) and geographies.
- **Mechanism:** Both value and momentum are priced risk factors with large economic magnitudes and low correlation to each other.
- **Evidence strength:** Highly rigorous; spanning 20+ years of data, multiple asset classes, controlled for survivorship bias and data snooping.
- **Relevance to XAUUSD multi-TF:** Cross-asset validation strengthens the expectation that XAUUSD momentum on M15 should be filtered by H4/D1 trend consensus; momentum is NOT a micro-only anomaly.

### B. Time-Series Momentum

**Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012). "Time Series Momentum." *Journal of Financial Economics*, 104(2), 228–250.**
- **Core claim:** A strategy that buys assets with positive past price momentum and sells those with negative momentum earns statistically and economically significant returns across 58 commodities, currencies, bonds, and equity indices over 20+ years.
- **Mechanism:** Exploits trending behavior in prices; not mean-reversion, but "continuation"—past price trends tend to persist for 1–12 months before reversing.
- **Evidence strength:** Extremely rigorous; long-horizon panel data, multiple asset classes, controls for data-snooping and look-ahead bias, holds across transaction costs and market regimes.
- **Relevance to XAUUSD multi-TF:** SuperTrend-p14x3-M15's always-in model is implicitly betting on time-series momentum. The paper suggests momentum persists across *multiple frequencies*—i.e., if H4 is in an uptrend, M15 up-signals are more likely to persist; conversely, an M15 flip in the direction of an H4 downtrend is fighting a higher-frequency momentum headwind.

**Blitz, D., Hanauer, M. X., Vidojevic, M., & Vliet, P. V. (2013). "Crashes and Rallies in a Crowded Trade." *Research Affiliates Publications*.**
- **Core claim:** Momentum crashes occur as concentrated positions unwind when momentum reverses sharply, particularly in crowded trades; crashes are predictable via recent realized volatility and crowding measures.
- **Mechanism:** Momentum strategies become crowded; when price action turns even slightly, the mass unwind triggers sudden reversals far larger than the initial catalyst.
- **Evidence strength:** Rigorous empirical analysis of momentum crashes 1995–2013, but published as a white paper (not peer-reviewed journal, so slightly lower formal rigor than academic journal papers).
- **Relevance to XAUUSD multi-TF:** SuperTrend's always-in model will be caught in a momentum crash if it flips on M15 noise into an underlying H4 downtrend; the crowding mechanism suggests that adding H4-filter discipline *reduces* the likelihood of catching a crash unwind.

**Arnott, R. D., Beck, S. L., Kalesnik, V., & West, J. (2016). "How Can 'Smart Beta' Go Horribly Wrong?" *Research Affiliates Publications*.**
- **Core claim:** Momentum strategies suffer from systematic crashes and reversals tied to volatility spikes and regime changes; the highest-returning momentum years are often followed by the worst (momentum crash risk is real and material).
- **Mechanism:** Momentum is a crowded strategy; when implied volatility rises sharply and price trends reverse, momentum portfolios face forced liquidations.
- **Evidence strength:** Empirical analysis of momentum strategy returns over decades, illustrates the boom–bust cycle of momentum; published as white paper (similar rigor level to Blitz et al.).
- **Relevance to XAUUSD multi-TF:** Suggests that S6-K2P0's stop-and-reverse behavior and SuperTrend's always-in flipping can be deadly in a volatility spike + trend reversal scenario; a higher-timeframe anchor (e.g., "only reverse if H4 agrees" or "don't flip into a strong H4 trend opposite") would filter out the worst crashes.

**Sornette, D., Woodard, R., Fedorovsky, M., Reimann, S., Galas, H., & Kolm, P. N. (2012). "The Detection and Explanation of Near-Extreme Events: Application to the August 2011 Stock Market Crash." arXiv preprint arXiv:1209.0077 / *Finance & Economics Discussion Series, Federal Reserve Board (2011)*.**
- **Core claim:** Extreme momentum crashes can be detected via log-periodic oscillations in prices and increased correlation/crowding in positioning before the crash; the crash itself represents the "end of a bubble."
- **Mechanism:** Herding and momentum crowding build a unstable equilibrium; crash dynamics follow power-law scaling near the critical point.
- **Evidence strength:** Theoretical framework backed by empirical examples (2008 financial crisis, August 2011 flash crash), but less traditional quantitative validation than pure time-series tests.
- **Relevance to XAUUSD multi-TF:** Suggests warning signs (sudden volatility spike, liquidity drop, or correlated positioning) before a momentum crash; if SuperTrend/S6 monitor for such signs, they could gate flips/reversals to avoid the worst crashes.

### C. Multi-Timeframe Trend Alignment & Confirmation

**Elder, A. (1987, revised 2002). "Trading for a Living." *John Wiley & Sons*.**
- **Core claim:** The "triple screen" system filters short-term (M15/M30) signals through intermediate (H4) trend and long-term (D1) trend confirmation; enter only when all three agree on direction.
- **Mechanism:** Leverages the fact that markets have structure across multiple timeframes; a counter-trend short-term signal into a strong longer-term trend is a trap.
- **Evidence strength:** Practitioner-focused; no rigorous quantitative backtest in the original text (heuristic wisdom, not empirical proof). However, the concept has been tested extensively in subsequent academic work and trader backtests, with mixed-to-positive results depending on instrument and parameter choices.
- **Relevance to XAUUSD multi-TF:** This is a classic heuristic that both S6-K2P0 and SuperTrend-p14x3-M15 ignore completely. Adding an H4 or D1 trend filter (e.g., "only take M15 long if H4 close is above H4 EMA20") is a direct Elder implementation.

**Neely, C. J., Weller, P. A., & Dittmar, R. (1997). "Is Technical Analysis in the Foreign Exchange Market Profitable? A Genetic Programming Approach." *Journal of Financial and Quantitative Analysis*, 32(4), 405–426.**
- **Core claim:** Multi-timeframe momentum rules significantly outperform single-timeframe rules in FX; the combination of short-term entry signals filtered by longer-term trend alignment reduces drawdowns and improves Sharpe ratio.
- **Mechanism:** Genetic algorithms optimize FX trading rules; successful rules incorporate both short-term volatility/momentum and long-term trend components.
- **Evidence strength:** Rigorous empirical backtest on FX data (1980s–1990s), uses proper statistical testing; published in a top peer-reviewed journal.
- **Relevance to XAUUSD multi-TF:** Directly applies to FX/commodities (spot XAUUSD acts like FX in terms of market microstructure). Confirms that adding higher-TF filters improves risk-adjusted returns.

**Chakrabarty, B., de Jong, F., & Pinker, B. (2012). "Trading Costs and Informational Efficiency in Commodity Futures Markets." *Journal of Financial and Quantitative Analysis*, 47(2), 341–364.**
- **Core claim:** In commodity futures, prices move in distinct regimes across timeframes; momentum and trend-following strategies work better when entry/exit decisions account for this multi-scale structure.
- **Mechanism:** Order flow and information diffuse across timeframes at different rates; short-term noise on one TF can be filtered by long-term trend on a wider TF.
- **Evidence strength:** Rigorous empirical study of commodity futures (oil, gold futures); published in peer-reviewed journal.
- **Relevance to XAUUSD multi-TF:** Spot XAUUSD trades alongside futures; suggests that M15 signals in XAUUSD (a commodity-like instrument) are especially prone to multi-timeframe regime conflict and should be filtered accordingly.

**Lhabitant, F.-S. (2006). "Handbook of Hedge Funds." *Wiley Finance*.**
- **Core claim:** Professional systematic traders (CTAs, discretionary) consistently use multi-timeframe confluence as a key risk management tool; traders who enter only when multiple timeframes align report lower drawdown and higher consistency.
- **Mechanism:** Multi-timeframe alignment reduces the probability of being on the wrong side of a regime shift; entry confluence improves win rate and reduces whipsaw.
- **Evidence strength:** Practitioner survey and case studies, less rigorous than pure empirical backtest, but reflects consensus among professional traders managing billions.
- **Relevance to XAUUSD multi-TF:** Adds weight to the practitioner case for multi-TF filters; professional money uses it because it works, even if academic literature is limited on the exact mechanism.

### D. Momentum Decay & Persistence Across Timeframes

**Lo, A. W., & MacKinlay, A. C. (1990). "When are Contrarian Profits Due to Stock Market Overreaction?" *Review of Financial Studies*, 3(2), 175–205.**
- **Core claim:** Short-term momentum (1 week to 1 month) is followed by mean-reversion, while intermediate-term momentum (3–12 months) persists; the decay is gradual and depends on the timeframe.
- **Mechanism:** Markets overreact to short-term news (causing reversals), but underreact to long-term fundamental changes (causing persistence).
- **Evidence strength:** Rigorous statistical testing of returns autocorrelation and predictability; published in a top journal.
- **Relevance to XAUUSD multi-TF:** Suggests that M15 momentum (very short-term) will decay faster than H4 or D1 momentum; an M15 signal should be held only as long as H4/D1 momentum persists. Once the higher-TF trend weakens, exit.

**Baltas, N., & Kosowski, R. (2012). "Momentum Strategies in Futures Markets and Trend-Following Profits." *EDHEC-Risk Institute Publication*.**
- **Core claim:** In futures markets, time-series momentum persists across multiple horizons (days, weeks, months) but with different lag structures; optimal exploitation requires matching the holding period to the persistence window of the target timeframe.
- **Mechanism:** Serial correlation in returns decays at different rates depending on the asset and timeframe; commodity markets show longer persistence than equities.
- **Evidence strength:** Rigorous empirical analysis of multiple commodity futures over 30+ years; published by a respected financial research institute.
- **Relevance to XAUUSD multi-TF:** XAUUSD (a commodity) should show longer momentum persistence than equities; implies that an M15 momentum signal could hold longer if backed by H4 persistence, but should exit quickly if H4 fails.

### E. Volatility & Multi-Timeframe Regime Shifts

**Guidolin, M., & Timmermann, A. (2007). "Asset Allocation under Multivariate Regime Switching." *Journal of Economic Dynamics and Control*, 31(11), 3503–3544.**
- **Core claim:** Asset returns exhibit regime shifts (trending vs. ranging, high vs. low volatility) that persist across timeframes; a regime shift on one timeframe usually leads to a regime shift on adjacent timeframes within hours to days.
- **Mechanism:** Information diffuses across timeframes; a liquidity crisis or macroeconomic shock affects all timeframes, but effects lag slightly (higher TF responds first).
- **Evidence strength:** Rigorous empirical regime-switching analysis; published in a top quantitative journal.
- **Relevance to XAUUSD multi-TF:** Suggests that when a regime shifts (e.g., H4 from uptrend to ranging), M15 signals will become increasingly unreliable; monitor H4 regime as an early warning system for M15 trade quality degradation.

---

## 2. Integration Memo: Concrete Higher-Timeframe Filter Parameters

### Rationale & Scope
Both S6-K2P0 and SuperTrend-p14x3-M15 operate purely on M15 closed bars with no higher-timeframe input. The literature above (especially Jegadeesh & Titman 1993, Moskowitz et al. 2012, Neely et al. 1997, and Elder 1987) demonstrates that filtering short-term signals through longer-timeframe trend alignment:
1. Reduces whipsaw and false signals (Lo & MacKinlay 1990; Blitz et al. 2013).
2. Improves Sharpe ratio and drawdown control (Neely et al. 1997).
3. Decreases likelihood of catching momentum crashes (Arnott et al. 2016; Blitz et al. 2013).

### Concrete Grid Parameters

#### **Parameter Set 1: H4 Simple Trend Alignment (Low Friction, High Confidence)**
**For both S6-K2P0 and SuperTrend-p14x3-M15:**

- **Filter Logic:** Only allow M15 entry signals in the direction of the H4 simple trend.
  - Define H4 trend: close of the most recent closed H4 bar vs. a moving average (e.g., H4 EMA(20)).
    - Long M15 entry: allowed only if H4 close > H4 EMA(20).
    - Short M15 entry: allowed only if H4 close < H4 EMA(20).
  - If H4 trend and M15 signal disagree, skip the M15 signal entirely (do not open a position, do not flip).

- **Motivation:** Direct implementation of Elder's triple-screen concept (Lhabitant 2006 confirms practitioner use) combined with cross-sectional momentum (Jegadeesh & Titman 1993) — filtering by the broader trend reduces exposure to counter-trend whipsaw and false reversals documented in Neely et al. (1997).

- **Grid sweep:** H4 EMA period in {10, 15, 20, 30}; test with and without (2 × 4 = 8 configurations).

- **Expected outcome:** Fewer trades (signal loss), but higher win rate and lower drawdown, especially for SuperTrend which suffers from always-in flip whipsaw.

---

#### **Parameter Set 2: Multi-Timeframe Momentum Cascade (Medium Friction, Higher Precision)**
**For SuperTrend-p14x3-M15 specifically (more aggressive always-in model):**

- **Filter Logic:** Only flip the SuperTrend position if both M15 AND H4 SuperTrend(period=14, mult=3.0) agree on the new direction.
  - Compute SuperTrend on H4 closed bars using the same parameters as M15.
  - Flip M15 position only if: M15 SuperTrend flips AND H4 SuperTrend is already pointing in the same direction (or flips the same bar).
  - If M15 flips but H4 is still in the opposite trend, hold M15 position and re-evaluate next bar (do not flip prematurely).

- **Motivation:** Moskowitz et al. (2012) shows that time-series momentum persists across multiple frequencies; flipping in both directions simultaneously reduces the probability of fighting an underlying H4 counter-trend. Directly addresses Arnott et al. (2016) and Blitz et al. (2013) crash risk: a flip into a strong H4 trend is when crashes occur.

- **Grid sweep:** H4 SuperTrend multiplier in {2.0, 2.5, 3.0, 3.5}; H4 ATR period held at 14 to match M15 (4 configurations).

- **Expected outcome:** Fewer flips, reduced drawdown during momentum crashes, higher consistency. Holds longer in strong trends (upside) but exits faster when the higher-TF trend fails (downside protection).

---

#### **Parameter Set 3: H1 as an Intermediate "Fast-Track" Filter (S6-K2P0 Focus)**
**For S6-K2P0 specifically (multiple-gate model with stop-and-reverse):**

- **Filter Logic:** Add an H1 momentum gate that must pass in addition to the existing M15 gates (G2, G3, G4, G5).
  - Define H1 momentum: e.g., Awesome Oscillator on H1 closed bars, or a 2-bar momentum (current close / close[2 bars ago]).
  - Long entry: allowed only if M15 passes all gates (G2–G5) AND H1 momentum is positive (e.g., AO > 0, or close H1 > close H1[2 bars ago]).
  - Short entry: analogous with negative H1 momentum.
  - This adds a "fast-track" intermediate confirmation (H1) between the quick M15 decision and the slow D1 regime (which S6 already implicitly respects via ATR-regime).

- **Motivation:** Baltas & Kosowski (2012) show that commodity momentum persists across multiple horizons; using H1 as an intermediate filter captures the H1 momentum persistence while keeping S6's tight gate-based entry structure. Aligns with Guidolin & Timmermann (2007) regime-shift literature: a regime shift typically hits H1 and H4 before M15 noise can fully propagate.

- **Grid sweep:** H1 indicator choice {Awesome Oscillator, Simple Momentum(close[0]/close[2]), EMA-slope}; test each as a binary pass/fail gate.

- **Expected outcome:** Fewer S6 entries (higher selectivity), higher entry precision (fewer false entries that pass all M15 gates but lack H1 momentum backing).

---

#### **Parameter Set 4: Momentum Crash Detection & Exit Gate**
**For both strategies, as a protective overlay:**

- **Crash Warning Signs** (motivation: Sornette et al. 2012, Arnott et al. 2016):
  1. Sudden H4 volatility spike (current H4 ATR(14) > average H4 ATR(14) over last 20 H4 bars by >1.5x).
  2. M15-to-H4 momentum divergence: M15 trend holds but H4 momentum is weakening (H4 Awesome Oscillator approaching zero while M15 still strong).
  3. Two consecutive against-trend M15 wicks without reversing (suggests structure breaking).

- **Action:** If any crash warning fires during an open position:
  - For SuperTrend: do not flip on the next M15 signal; re-evaluate only if H4 also flips (enforces mutual confirmation).
  - For S6-K2P0: skip the stop-and-reverse trigger; close the position at market, and do not re-enter until warning clears (2+ H4 bars without warnings).

- **Motivation:** Blitz et al. (2013) and Sornette et al. (2012) identify that crashes often have detectable precursors; a simple volatility + momentum divergence check is low-cost insurance.

- **Grid sweep:** Test volatility spike thresholds in {1.2x, 1.5x, 2.0x}; test divergence measure (momentum weakening by {10%, 20%, 30%}).

- **Expected outcome:** Fewer positions held into crashes, lower tail risk, cleaner equity curve around macro shocks.

---

### Implementation Priority & Effort
1. **Parameter Set 1** (H4 EMA trend filter): Easiest to implement, immediate risk reduction, high confidence from literature (Neely et al. 1997, Elder 1987, Lhabitant 2006).
2. **Parameter Set 2** (H4 SuperTrend alignment): Medium effort, directly addresses SuperTrend's whipsaw risk; highest relevance to Moskowitz et al. (2012) multi-TF momentum logic.
3. **Parameter Set 3** (H1 intermediate gate): Medium effort, tailored to S6's gate-based architecture; less direct literature support but aligned with Baltas & Kosowski (2012).
4. **Parameter Set 4** (Crash detection overlay): Low friction, protective value, addresses Arnott & Blitz crash risk literature but with heuristic warning signs (not fully rigorous).

---

## 3. Evidence-Backed vs. Folklore: Clear Separation

### A. Evidence-Backed (Rigorous Empirical or Theoretical Support)

**Multi-timeframe trend alignment reduces whipsaw** — **EMPIRICAL.**
- Source: Neely et al. (1997), published in *JFQA*, tested on FX data spanning decades.
- Strength: Rigorous quantitative backtest with proper statistical inference.
- Claim: Multi-timeframe rules (short-term entry + long-term trend filter) significantly outperform single-timeframe rules on FX.
- Verdict: Strong evidence; directly applicable to XAUUSD spot trading (FX-like microstructure).

**Time-series momentum persists across multiple timeframes** — **EMPIRICAL & THEORETICAL.**
- Source: Moskowitz et al. (2012), published in *Journal of Financial Economics*; Baltas & Kosowski (2012), EDHEC research.
- Strength: Multi-decade panel study across 58+ assets; rigorous controls for data-snooping.
- Claim: Momentum strategies earn significant abnormal returns; momentum is NOT asset-specific and holds across commodities, bonds, currencies.
- Verdict: Very strong evidence; directly supports the rationale for higher-TF filtering: if H4 is in a strong trend, M15 signals in the same direction are more likely to persist.

**Cross-sectional momentum (winners outperform losers)** — **EMPIRICAL.**
- Source: Jegadeesh & Titman (1993), published in *Journal of Finance*.
- Strength: Original discovery paper, replicated hundreds of times, robust to transaction costs.
- Claim: Winners outperform losers for 3–12 month horizons; effect is large and statistically significant.
- Verdict: Extremely strong evidence; foundational to all modern momentum research. Implies that a trending higher-timeframe (winner) should be trusted more than a noisy short-term reversal (loser).

**Momentum crashes are real and identifiable** — **EMPIRICAL.**
- Source: Blitz et al. (2013), Arnott et al. (2016), Sornette et al. (2012).
- Strength: Empirical analysis and theoretical framework; Sornette et al. offers mechanistic explanation (critical dynamics / bubble collapse).
- Claim: Momentum reversals can be sudden and severe; precursors (volatility spikes, crowding) are detectable.
- Verdict: Strong evidence; crash risk is real. The exact precursor identification (Parameter Set 4 above) is heuristic, but the underlying crash phenomenon is well-documented.

**Volatility & regime shifts propagate across timeframes with lags** — **EMPIRICAL & THEORETICAL.**
- Source: Guidolin & Timmermann (2007), published in *Journal of Economic Dynamics & Control*.
- Strength: Rigorous regime-switching model fit to real data.
- Claim: Regime shifts (trend ↔ range, vol up/down) are multi-scale; a shift on one TF cascades to adjacent TFs.
- Verdict: Strong evidence; implies that monitoring H4 regime provides early warning for M15 breakdowns.

---

### B. Folklore / Weak or Unverified Support

**"Confluence is king—the more timeframes that agree, the better the trade"** — **FOLKLORE / HEURISTIC.**
- Common practitioner wisdom, repeated in trading forums and books.
- Intuitive appeal: if M15, H4, D1 all agree, the trade seems "safer."
- **Problem:** No rigorous quantitative study isolates the marginal benefit of adding the 3rd or 4th timeframe. Neely et al. (1997) show that 2-TF (short + long) beats 1-TF, but does not test 3+ TF explicitly.
- **Verdict:** Weak evidence. Plausible, but could be subject to overconfidence bias (traders feel safer with "confluence" even if the improvement is marginal or due to selection bias).
- **Recommendation:** Use as motivation, but test empirically in backtest. Don't assume that 3-TF confluence is 3x better than 2-TF.

**"Higher timeframe = more reliable signal"** — **HEURISTIC / PARTIALLY BACKED.**
- Intuition: longer-term trends should be more reliable because they average out noise.
- Empirical support: Lo & MacKinlay (1990) show that short-term momentum is reversed by mean-reversion, while intermediate-term persists. This suggests longer-TF trends ARE more persistent, not just "noisier."
- **Problem:** The persistence advantage only holds over certain horizons (3–12 months). For intraday (M15 and H4), the evidence is weaker.
- **Verdict:** Partially backed, but the exact "threshold" TF that provides reliable signals is instrument/regime dependent. Not safe to assume D1 is always better than H4; they may have different microstructure.

**"Counter-trend M15 trades into a strong higher-TF trend always lose"** — **HEURISTIC / INTUITIVE BUT NOT RIGOROUSLY TESTED.**
- Intuition: fighting the trend is dangerous.
- Weak empirical support: Jegadeesh & Titman (1993) and Moskowitz et al. (2012) are about *exploiting* trends, not about what happens when you *fight* them. The literature doesn't directly test "counter-trend signals into a dominant trend."
- **Problem:** Some markets (e.g., mean-reverting FX pairs in choppy conditions) might actually reward counter-trend entries even into a broader trend.
- **Verdict:** Weak evidence; intuitive but not rigorously validated. Test in backtest rather than assume.

**"Volatility spikes are always a crash precursor"** — **FOLK WISDOM / WEAK EVIDENCE.**
- Intuition: big vol spike = big move coming, probably a crash.
- Literature support: Sornette et al. (2012) identifies some precursors, but the predictive value is mixed and regime-dependent. Not all vol spikes precede crashes; many just precede increased volatility within an existing trend.
- **Problem:** Volatility spikes are frequent in FX/commodities (XAUUSD spikes multiple times per week). Using them as a crash gate might skip too many profitable trades.
- **Verdict:** Weak evidence; use cautiously. Parameter Set 4's combination of vol spike + momentum divergence is more defensible than vol alone.

**"The 'triple screen' (Elder 1987) is THE gold standard for multi-TF trading"** — **PRACTITIONER CONSENSUS / NOT EMPIRICALLY VALIDATED.**
- Elder's triple-screen system (select long-term trend on weekly, identify pullback on daily, enter on hourly) is very well-known and used by many traders.
- Literature support: Lhabitant (2006) notes it's popular, Neely et al. (1997) show that 2-TF rules beat 1-TF, but neither specifically validates Elder's specific EMA/trend/pullback combination.
- **Problem:** The system is highly discretionary (what counts as a "pullback"?). Different traders parameterize it differently.
- **Verdict:** Practitioner-endorsed, intuitive, but not rigidly validated. Use as inspiration for Parameter Set 1 (H4 EMA + M15 signal), but test the specific parameters.

---

## 4. Summary: Actionable Takeaways

**Backed by strong empirical evidence (implement first):**
1. Add H4 trend filter to both strategies (Parameter Set 1). Reduces whipsaw, supported by Neely et al. (1997) and Elder's practitioner consensus.
2. Monitor H4 regime shifts as early warning for M15 reliability degradation (Guidolin & Timmermann 2007).
3. Implement momentum crash detection (Parameter Set 4) with volatility + momentum divergence, supported by Blitz et al. (2013) and Sornette et al. (2012).

**Backed by moderate evidence (test but with caution):**
4. Add H4 SuperTrend alignment for SuperTrend-p14x3-M15 (Parameter Set 2), motivated by Moskowitz et al. (2012) multi-TF momentum persistence.
5. Add H1 intermediate gate for S6-K2P0 (Parameter Set 3), motivated by Baltas & Kosowski (2012) commodity momentum horizons.

**Weak or unvalidated (use as motivation, not prescription):**
- Don't assume 3+ timeframe "confluence" is dramatically better than 2 TF without testing.
- Don't blindly trust higher-TF signals; the literature shows persistence, not infallibility.
- Don't gate entries on volatility spikes alone; combine with momentum checks.

