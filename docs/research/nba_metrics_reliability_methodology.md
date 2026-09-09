# Reliability Measurement Methodology

## Overview

This document explains how reliability scores were assigned to each NBA advanced metric, the criteria used for classification, and the justification for each threshold. The methodology draws on established practices in sports analytics, statistics, and machine learning validation.

**Note:** This methodology document has been updated to include metrics added in the revised reports (APM, PIPM, TPA, DARKO, CARMELO).

---

## 1. Definition of Reliability

**Reliability** in this context refers to a metric's ability to accurately and consistently capture true player or team impact on basketball outcomes (primarily winning). A reliable metric should:

1. **Correlate strongly with team success** (wins, point differential)
2. **Predict future performance** (out-of-sample validity)
3. **Remain stable across samples** (low standard error, narrow confidence intervals)
4. **Account for context** (teammates, opponents, pace, role)
5. **Capture all relevant aspects of the game** (offense, defense, playmaking, rebounding)

---

## 2. Criteria for Defining Reliability

Six primary criteria were used to evaluate and score each metric:

### 2.1 Out-of-Sample Predictive Accuracy

**Definition:** The metric's ability to predict future outcomes (team wins, future RAPM) when trained on historical data.

**Measurement Method:**

- Split data into training (70-80%) and testing (20-30%) sets [SRC-65][SRC-67]
- Train the metric on historical data
- Test predictions on unseen data
- Measure correlation (r) or prediction error (RMSE) between predicted and actual outcomes

**Thresholds:**

| Reliability Tier | Correlation with Wins | RMSE (Game Margin) |
|-----------------|----------------------|-------------------|
| High (85-95%) | r > 0.80 | < 12 points |
| Moderate-High (75-85%) | r = 0.65-0.80 | 12-15 points |
| Moderate (60-75%) | r = 0.50-0.65 | 15-18 points |
| Low-Moderate (50-65%) | r < 0.50 | > 18 points |

**Evidence:**

- Four-year study [SRC-67] measured correlation between team-aggregated player metrics and team wins:
  - WS/48: 83.1% (High)
  - RPM: 81.9% (High)
  - Rtg: 81.5% (High)
  - BPM: 79.1% (Moderate-High)
  - WS: 76.9% (Moderate-High)
  - VORP: 75.3% (Moderate-High)
  - PER: 67.5% (Moderate)

**Why This Criterion:**

Out-of-sample testing is the gold standard in machine learning and predictive modeling [SRC-39][SRC-65]. A metric that performs well on training data but poorly on test data is overfitting and will not generalize to new observations.

**Special Case: Projection Systems (CARMELO)**

- CARMELO forecasts career trajectories, not single-season impact [SRC-97][SRC-137]
- Not directly comparable to impact metrics (answers different question)
- Rated separately as "N/A" rather than assigned a reliability tier [SRC-97][SRC-137]

---

### 2.2 Standard Error / Confidence Interval Width

**Definition:** The statistical uncertainty associated with a metric's estimate for a given player or team.

**Measurement Method:**

- Compute standard errors via bootstrap resampling or Taylor-series approximation [SRC-68][SRC-69][SRC-84]
- Calculate 95% confidence intervals: estimate ± 1.96 × SE
- Measure CI width relative to the estimate

**Thresholds:**

| Reliability Tier | 95% CI Width (per 100 poss) | Multi-year SE Reduction |
|-----------------|----------------------------|------------------------|
| High (85-95%) | < 3.0 points | > 75% reduction |
| Moderate-High (75-85%) | 3.0-6.0 points | 50-75% reduction |
| Moderate (60-75%) | 6.0-9.0 points | 25-50% reduction |
| Low-Moderate (50-65%) | > 9.0 points | < 25% reduction |

**Evidence:**

- Multi-year RAPM standard errors decrease ~80% compared to single-season data [SRC-40]
- Kyle Korver's 95% CI: [-1.21, 4.16] (width = 5.37 points) [SRC-73]
- Standard errors for box-score metrics can be computed via Taylor-series method [SRC-69][SRC-84]
- APM requires thousands of games to achieve stability due to multicollinearity [SRC-91][SRC-92]

**Why This Criterion:**

Standard errors quantify uncertainty. A player with RAPM = +5.0 ± 1.5 is meaningfully different from a player with RAPM = +5.0 ± 4.0, even though both have the same point estimate [SRC-68][SRC-73]. Metrics with narrow CIs are more actionable for decision-making.

**Special Case: DARKO**

- DARKO uses Kalman filtering, which inherently provides uncertainty estimates [SRC-109][SRC-111]
- Exponential decay appropriately weights recent performance, reducing noise [SRC-124][SRC-133]
- Estimated reliability: 85-90% based on academic validation [SRC-111]

---

### 2.3 Correlation with Team Success

**Definition:** The strength of association between a player metric (aggregated to team level) and team outcomes (wins, point differential).

**Measurement Method:**

- Aggregate player metric to team level (weighted by minutes)
- Correlate with team wins or point differential
- Use Pearson's r or R²

**Thresholds:**

| Reliability Tier | Correlation (r) | R² |
|-----------------|----------------|-----|
| High (85-95%) | r > 0.80 | R² > 0.64 |
| Moderate-High (75-85%) | r = 0.65-0.80 | R² = 0.42-0.64 |
| Moderate (60-75%) | r = 0.50-0.65 | R² = 0.25-0.42 |
| Low-Moderate (50-65%) | r < 0.50 | R² < 0.25 |

**Evidence:**

- Team PIE R² = 0.908 with winning percentage [SRC-1]
- WS/48 correlation = 83.1% (r = 0.831) [SRC-67]
- RPM correlation = 81.9% (r = 0.819) [SRC-67]
- PER correlation = 67.5% (r = 0.675) [SRC-67]
- Four Factors explain ~95% of variance in offensive efficiency [SRC-46][SRC-77]
- PIPM R² = 0.875 with 15-year RAPM [SRC-113]

**Why This Criterion:**

Basketball is a team sport; individual impact should manifest in team success. Metrics that correlate strongly with wins are capturing something real about player contribution [SRC-17][SRC-21][SRC-67].

**Special Case: PIPM**

- PIPM R² = 0.875 with RAPM indicates strong alignment [SRC-113]
- Described as "one of the most accurate publicly available impact metrics in terms of predicting future results" [SRC-90]
- Estimated reliability: 80-85% (Tier 2)

---

### 2.4 Methodological Transparency & Validation

**Definition:** The extent to which a metric's formula, assumptions, and validation process are publicly documented and independently reproducible.

**Measurement Method:**

- Check if full formula is published
- Check if methodology is peer-reviewed or independently validated
- Check if third parties have replicated results

**Thresholds:**

| Reliability Tier | Documentation Level | Independent Replication |
|-----------------|--------------------|------------------------|
| High (85-95%) | Full formula + validation details | Yes, multiple studies |
| Moderate-High (75-85%) | Full formula, limited validation | Yes, 1-2 studies |
| Moderate (60-75%) | Partial formula, no validation | No |
| Low-Moderate (50-65%) | Black box or minimal documentation | No |

**Evidence:**

- **High:** BPM (full formula on Basketball Reference, Myers provides detailed documentation) [SRC-47]
- **Moderate-High:** EPM (core methodology described, but full optimization details not public) [SRC-36][SRC-39]; PIPM (three components publicly documented) [SRC-113][SRC-127]; DARKO (used in academic research, but full details not public) [SRC-111][SRC-133]
- **Moderate:** RAPTOR (general approach described, but exact weights not public) [SRC-80][SRC-87]; CARMELO (general methodology public, but discontinued) [SRC-97][SRC-106]
- **Low-Moderate:** Some proprietary metrics (no public formula)

**Why This Criterion:**

Transparency enables scrutiny, replication, and improvement. Black-box metrics cannot be independently validated, making it impossible to assess whether they're capturing signal or noise [SRC-39][SRC-47].

**Special Case: CARMELO**

- CARMELO methodology publicly documented by FiveThirtyEight [SRC-97][SRC-99][SRC-106]
- However, discontinued ~2020, replaced by RAPTOR [SRC-80][SRC-87]
- Rated separately as "N/A" (projection system, not impact metric) [SRC-97][SRC-137]

---

### 2.5 Context Adjustment

**Definition:** The extent to which a metric controls for external factors that affect raw statistics (pace, teammate quality, opponent quality, role).

**Measurement Method:**

- Check if metric adjusts for pace (per-100-possession or per-minute)
- Check if metric adjusts for teammate quality (on/off, regression)
- Check if metric adjusts for opponent quality (strength of schedule, opponent adjustments)
- Check if metric adjusts for role (usage, position)

**Thresholds:**

| Reliability Tier | Pace Adjustment | Teammate Adjustment | Opponent Adjustment | Role Adjustment |
|-----------------|----------------|--------------------|--------------------|----------------|
| High (85-95%) | Yes | Yes (regression/on-off) | Yes | Yes |
| Moderate-High (75-85%) | Yes | Yes (partial) | Yes (partial) | Yes (partial) |
| Moderate (60-75%) | Yes | No or minimal | No | No |
| Low-Moderate (50-65%) | No | No | No | No |

**Evidence:**

- **High:** RAPM (adjusts for all four via lineup regression) [SRC-34][SRC-44]; EPM (adjusts for all four via Estimated Skills + RAPM) [SRC-36][SRC-71]; DARKO (adjusts for all four via Kalman filtering + exponential decay) [SRC-111][SRC-124][SRC-133]; PIPM (adjusts for all four via box prior + luck-adjusted on/off) [SRC-90][SRC-113][SRC-127]
- **Moderate-High:** BPM (adjusts for pace and role via position-aware coefficients; limited teammate/opponent adjustment) [SRC-47]
- **Moderate:** PER (adjusts for pace; no teammate/opponent/role adjustment) [SRC-16][SRC-30]
- **Low-Moderate:** Raw box score stats (no adjustments) [SRC-4][SRC-12]; APM (adjusts for teammates/opponents via regression, but unstable due to multicollinearity) [SRC-88][SRC-91][SRC-92]

**Why This Criterion:**

Raw statistics are heavily confounded by context. A player averaging 20 PPG on a fast-paced team with weak teammates is not equivalent to a player averaging 20 PPG on a slow-paced team with strong teammates [SRC-30][SRC-47]. Metrics that adjust for context isolate individual contribution from environmental factors.

**Special Case: APM**

- APM adjusts for teammates and opponents via OLS regression [SRC-88][SRC-91]
- However, severe multicollinearity makes estimates unstable [SRC-89][SRC-92]
- Requires thousands of games to achieve stability [SRC-91][SRC-92]
- Superseded by RAPM, which applies ridge regression [SRC-34][SRC-89][SRC-94]
- Reliability: 50-60% (Tier 4) despite context adjustment, due to instability [SRC-89][SRC-92]

---

### 2.6 Defensive Capture

**Definition:** The extent to which a metric captures defensive impact beyond box score stats (steals, blocks, defensive rebounds).

**Measurement Method:**

- Check if metric uses tracking data (contested shots, defensive positioning)
- Check if metric uses on/off data (points allowed when player is on court)
- Check if metric uses RAPM (which captures all scoring impact, including defense)
- Check if metric is box-score-only (STL, BLK, DRB only)

**Thresholds:**

| Reliability Tier | Tracking Data | On/Off Data | RAPM Component | Box Score Only |
|-----------------|--------------|------------|---------------|----------------|
| High (85-95%) | Yes | Yes | Yes | No |
| Moderate-High (75-85%) | Yes or On/Off | Yes or RAPM | Yes | No |
| Moderate (60-75%) | No | Partial | No | Partial |
| Low-Moderate (50-65%) | No | No | No | Yes |

**Evidence:**

- **High:** EPM (uses RAPM, which captures all scoring impact including defense) [SRC-36][SRC-39]; RAPM (captures all scoring margin, including defensive impact) [SRC-34][SRC-44]; DARKO (uses RAPM family inputs) [SRC-111][SRC-133]; PIPM (uses luck-adjusted on/off data) [SRC-90][SRC-113][SRC-127]
- **Moderate-High:** BPM (box score only for defense; Myers explicitly states DBPM is unreliable) [SRC-47][SRC-54]
- **Low-Moderate:** PER (only STL/BLK; Hollinger admits it's not reliable for defense) [SRC-16][SRC-30]; APM (captures all scoring impact, but unstable) [SRC-88][SRC-91][SRC-92]

**Why This Criterion:**

Defense is notoriously difficult to quantify with box score stats alone. Steals and blocks capture only a fraction of defensive impact; positioning, communication, contesting shots, and forcing difficult attempts are equally important but invisible in traditional stats [SRC-47][SRC-54]. Metrics that incorporate on/off data or RAPM capture defensive impact more comprehensively.

**Special Case: TPA**

- TPA inherits BPM's defensive limitations (DBPM component) [SRC-108][SRC-122]
- "TPA is just BPM times minutes played" [SRC-108]
- Reliability: 70-75% (Tier 3), same as BPM [SRC-108]

---

## 3. Composite Reliability Score Calculation

Each metric was scored on all six criteria (0-100 scale per criterion), then averaged to produce a composite reliability score:
Composite Score = (Criterion1 + Criterion2 + Criterion3 + Criterion4 + Criterion5 + Criterion6) / 6

text

**Example Calculation: EPM**

| Criterion | Score (0-100) | Justification |
|-----------|--------------|---------------|
| Out-of-Sample Accuracy | 90 | Validated through out-of-sample testing against future RAPM [SRC-39] |
| Standard Error | 85 | Multi-year RAPM component; SE decreases ~80% with more data [SRC-40] |
| Correlation with Wins | 85 | Team EPM predicts game margins with RMSE = 12.1 points [SRC-36] |
| Transparency | 75 | Core methodology public, but full optimization details not [SRC-39] |
| Context Adjustment | 95 | Adjusts for pace, teammates, opponents, role via Estimated Skills + RAPM [SRC-36][SRC-71] |
| Defensive Capture | 90 | Uses RAPM, which captures all scoring impact including defense [SRC-36][SRC-44] |
| **Composite** | **86.7** | → Tier 1: High Reliability (85-95%) |

**Example Calculation: DARKO**

| Criterion | Score (0-100) | Justification |
|-----------|--------------|---------------|
| Out-of-Sample Accuracy | 90 | Used in academic research as most predictive public metric [SRC-111] |
| Standard Error | 85 | Kalman filtering provides uncertainty estimates; exponential decay reduces noise [SRC-109][SRC-124] |
| Correlation with Wins | 85 | Team DARKO ratings predict game margins (similar to EPM) [SRC-111][SRC-133] |
| Transparency | 70 | Used in academic research, but full methodology not completely public [SRC-111] |
| Context Adjustment | 95 | Adjusts for pace, teammates, opponents, role via Kalman filtering + RAPM inputs [SRC-111][SRC-124][SRC-133] |
| Defensive Capture | 90 | Uses RAPM family inputs, which capture all scoring impact including defense [SRC-111][SRC-118] |
| **Composite** | **85.8** | → Tier 1: High Reliability (85-95%) |

**Example Calculation: PIPM**

| Criterion | Score (0-100) | Justification |
|-----------|--------------|---------------|
| Out-of-Sample Accuracy | 85 | R² = 0.875 with 15-year RAPM; described as highly accurate for predicting future results [SRC-90][SRC-113] |
| Standard Error | 80 | Luck adjustment reduces noise; still subject to on/off noise for low-minute players [SRC-113][SRC-127] |
| Correlation with Wins | 80 | R² = 0.875 with RAPM (which correlates 81.9% with wins) [SRC-67][SRC-113] |
| Transparency | 85 | Three components publicly documented (box prior, luck-adjusted on/off, luck-adjusted net rating) [SRC-113][SRC-127][SRC-129] |
| Context Adjustment | 90 | Adjusts for pace, teammates, opponents, role via box prior + luck-adjusted on/off [SRC-90][SRC-113][SRC-126] |
| Defensive Capture | 80 | Uses luck-adjusted on/off data, but box prior inherits BPM defensive limitations [SRC-113][SRC-118] |
| **Composite** | **83.3** | → Tier 2: Moderate-High Reliability (75-85%) |

**Example Calculation: PER**

| Criterion | Score (0-100) | Justification |
|-----------|--------------|---------------|
| Out-of-Sample Accuracy | 55 | Correlation with wins = 67.5% [SRC-67] |
| Standard Error | 60 | No published SE; box-score-based, moderate noise |
| Correlation with Wins | 55 | r = 0.675 [SRC-67] |
| Transparency | 95 | Full formula public on Wikipedia [SRC-16] |
| Context Adjustment | 50 | Adjusts for pace only; no teammate/opponent/role adjustment [SRC-16][SRC-30] |
| Defensive Capture | 30 | Only STL/BLK; Hollinger admits not reliable for defense [SRC-16][SRC-30] |
| **Composite** | **57.5** | → Tier 4: Low-Moderate Reliability (50-65%) |

**Example Calculation: APM**

| Criterion | Score (0-100) | Justification |
|-----------|--------------|---------------|
| Out-of-Sample Accuracy | 50 | Unstable even in multi-year samples due to multicollinearity [SRC-89][SRC-92] |
| Standard Error | 40 | Requires thousands of games to achieve stability [SRC-91][SRC-92] |
| Correlation with Wins | 55 | RAPM (regularized version) correlates 81.9%; APM is less stable [SRC-67][SRC-89] |
| Transparency | 85 | Methodology publicly documented (OLS regression on lineup data) [SRC-88][SRC-91] |
| Context Adjustment | 80 | Adjusts for teammates and opponents via regression, but unstable [SRC-88][SRC-91][SRC-92] |
| Defensive Capture | 70 | Captures all scoring impact (including defense), but unstable [SRC-88][SRC-91] |
| **Composite** | **63.3** | → Tier 4: Low-Moderate Reliability (50-65%) due to instability |

**Example Calculation: CARMELO**

| Criterion | Score (0-100) | Justification |
|-----------|--------------|---------------|
| Out-of-Sample Accuracy | N/A | Forecasts career trajectories, not single-season impact [SRC-97][SRC-137] |
| Standard Error | N/A | Probabilistic forecasts provide uncertainty, but not directly comparable [SRC-105][SRC-138] |
| Correlation with Wins | N/A | CARM-Elo (team-level) performed well vs. Vegas spreads, but not single-season metric [SRC-110] |
| Transparency | 80 | General methodology public, but discontinued ~2020 [SRC-97][SRC-106] |
| Context Adjustment | 75 | Uses RPM (2/3) + BPM (1/3), which adjust for context [SRC-99][SRC-105] |
| Defensive Capture | 65 | Relies on RPM (discontinued) and BPM (box-score-only defense) [SRC-99][SRC-105] |
| **Composite** | **N/A** | → Not rated (projection system, not single-season impact metric) [SRC-97][SRC-137] |

---

## 4. Tier Boundaries

Tier boundaries were set based on natural breaks in the data and practical significance:

| Tier | Score Range | Interpretation |
|------|------------|----------------|
| **Tier 1: High Reliability** | 85-95% | Suitable for primary decision-making (player evaluation, roster construction) |
| **Tier 2: Moderate-High Reliability** | 75-85% | Suitable for secondary analysis; use in combination with other metrics |
| **Tier 3: Moderate Reliability** | 60-75% | Useful for descriptive purposes; limited predictive value |
| **Tier 4: Low-Moderate Reliability** | 50-65% | Use with extreme caution; significant flaws limit utility |
| **N/A: Not Comparable** | N/A | Projection systems (CARMELO) answer different questions than impact metrics |

**Rationale for Boundaries:**

- **85% threshold:** Metrics scoring ≥85% consistently demonstrate strong out-of-sample predictive accuracy (r > 0.80) and narrow confidence intervals, making them actionable for high-stakes decisions [SRC-36][SRC-39][SRC-67][SRC-111]
- **75% threshold:** Metrics scoring 75-85% show moderate predictive accuracy (r = 0.65-0.80) and are useful when combined with other metrics, but should not be used in isolation [SRC-47][SRC-67][SRC-90][SRC-113]
- **60% threshold:** Metrics scoring 60-75% have limited predictive value (r = 0.50-0.65) and are best used for descriptive purposes rather than evaluation [SRC-1][SRC-6][SRC-67][SRC-108]
- **<60%:** Metrics scoring <60% have significant methodological flaws (e.g., poor defensive capture, no context adjustment, instability) that severely limit their utility [SRC-16][SRC-30][SRC-54][SRC-67][SRC-89][SRC-92]

---

## 5. Special Cases

### 5.1 Projection Systems (CARMELO)

**Why Not Rated:**

- CARMELO forecasts **future career trajectories** (WARP), not current-season impact [SRC-97][SRC-102][SRC-135]
- Answers a fundamentally different question than impact metrics like EPM, RAPM, BPM [SRC-97][SRC-137]
- Discontinued by FiveThirtyEight (~2020), replaced by RAPTOR [SRC-80][SRC-87]

**Treatment:**

- Listed separately as "N/A" rather than assigned a reliability tier [SRC-97][SRC-137]
- Not included in ML model feature recommendations (different use case) [SRC-97][SRC-137]

---

### 5.2 Historical/Foundation Metrics (APM)

**Why Low Rating Despite Context Adjustment:**

- APM adjusts for teammates and opponents via OLS regression [SRC-88][SRC-91]
- However, severe multicollinearity makes estimates unstable [SRC-89][SRC-92]
- Requires thousands of games to achieve stability [SRC-91][SRC-92]
- Superseded by RAPM, which applies ridge regression to solve multicollinearity [SRC-34][SRC-89][SRC-94]

**Treatment:**

- Rated Tier 4 (50-60%) due to instability, despite context adjustment [SRC-89][SRC-92]
- Not recommended for modern player evaluation [SRC-34][SRC-89][SRC-94]
- Included for historical completeness (foundation for RAPM, RPM, EPM, etc.) [SRC-88][SRC-91]

---

### 5.3 Cumulative Metrics (TPA, VORP)

**Why Moderate Rating:**

- TPA ≈ BPM × minutes played [SRC-108]
- Inherits BPM's reliability (70-75%) [SRC-108]
- Additional limitation: Cumulative stats conflate quality and quantity [SRC-108]

**Treatment:**

- Rated Tier 3 (70-75%), same as BPM [SRC-108]
- Useful for total season contribution, but not for per-possession impact [SRC-108][SRC-121][SRC-122]
- Not recommended as primary feature in ML models (use rate metrics instead) [SRC-108]

---

## 6. Limitations of This Methodology

1. **Subjectivity in Scoring:** While criteria are defined objectively, assigning scores (0-100) involves some judgment. Different analysts might score the same metric differently.

2. **Data Availability:** Some metrics (EPM, RAPTOR, LEBRON, DARKO) do not publish full methodologies, making it impossible to fully evaluate transparency or replicate results [SRC-39][SRC-80][SRC-87][SRC-111].

3. **Era Dependence:** Reliability scores are based on modern NBA data (2010s-2020s). Metrics may perform differently in different eras (e.g., pre-three-point era, pre-tracking era) [SRC-30][SRC-61].

4. **Position Dependence:** Some metrics perform better for certain positions (e.g., BPM is better for offensive creators than defensive specialists) [SRC-47]. This analysis does not position-stratify reliability scores.

5. **Sample Size Requirements:** Reliability scores assume adequate sample sizes (e.g., 500+ minutes for player metrics). Metrics may be less reliable for low-minute players [SRC-34][SRC-40].

6. **Projection vs. Impact:** CARMELO and similar projection systems answer fundamentally different questions than single-season impact metrics and are not directly comparable [SRC-97][SRC-137].

---

## 7. Recommendations for ML Model Development

Based on this reliability analysis, the following approach is recommended for developing an ML model to quantify player impact:

### 7.1 Feature Selection

**Primary Features (Tier 1: High Reliability):**

- EPM (total, offensive, defensive) [SRC-36][SRC-39]
- DARKO (total, offensive, defensive) [SRC-111][SRC-133]
- RAPM (total, offensive, defensive) [SRC-34][SRC-44]
- Net Rating (team-level) [SRC-55][SRC-77]
- Four Factors (eFG%, TOV%, OREB%, FTR) [SRC-46][SRC-49][SRC-77]

**Secondary Features (Tier 2: Moderate-High Reliability):**

- PIPM (total, offensive, defensive) [SRC-90][SRC-113]
- RPM/LEBRON/RAPTOR (total, offensive, defensive) [SRC-37][SRC-78][SRC-80]
- BPM (offensive only; exclude or downweight DBPM) [SRC-47][SRC-54]
- Win Shares (WS/48; use with caution for defense) [SRC-17][SRC-67]
- TS%, AST%, REB% [SRC-10][SRC-15][SRC-76]

**Tertiary Features (Tier 3: Moderate Reliability):**

- PIE (player) [SRC-1][SRC-6]
- TPA (cumulative; use only if volume matters for specific use case) [SRC-108][SRC-121]
- VORP (cumulative; same caveat as TPA) [SRC-67]

**Exclude or Heavily Downweight (Tier 4: Low-Moderate Reliability):**

- PER [SRC-16][SRC-30][SRC-67]
- DBPM [SRC-47][SRC-54]
- APM [SRC-88][SRC-89][SRC-92]

**Do Not Include (Different Use Case):**

- CARMELO (projection system, not single-season impact) [SRC-97][SRC-137]

### 7.2 Uncertainty Quantification

- Incorporate standard errors/confidence intervals where available (especially for RAPM-based metrics) [SRC-68][SRC-69][SRC-73][SRC-84]
- Weight observations by reliability: Tier 1 metrics should have higher weight in the model
- Use Bayesian approaches to propagate uncertainty from input metrics to final impact estimates

### 7.3 Context Features

Include the following as control variables to adjust for context not fully captured in individual metrics [SRC-36][SRC-43][SRC-47]:

- Pace (team and opponent)
- Opponent strength (SRS, opponent Net Rating)
- Teammate quality (average EPM/RAPM/DARKO of teammates)
- Role (usage rate, position)

### 7.4 Validation Strategy

- Use k-fold cross-validation to assess out-of-sample predictive accuracy [SRC-44][SRC-65]
- Measure correlation with team wins and point differential [SRC-67]
- Compare model predictions to established metrics (EPM, RAPM, DARKO) to ensure consistency [SRC-39][SRC-111]

---

## 8. Conclusion

This methodology provides a transparent, evidence-based framework for evaluating the reliability of NBA advanced metrics. By scoring metrics across six criteria (out-of-sample accuracy, standard error, correlation with wins, transparency, context adjustment, defensive capture), we can identify which metrics are most suitable for different use cases (player evaluation, roster construction, ML modeling).

**Key Takeaways:**

1. **Metrics using lineup data with regularization (RAPM, EPM, DARKO, PIPM) are the most reliable** (80-90%), as they control for context and are validated through out-of-sample testing [SRC-34][SRC-36][SRC-39][SRC-44][SRC-111][SRC-113]
2. **Team-level metrics (Net Rating, Four Factors) are more reliable than individual metrics** (90-95% vs. 50-90%), as they aggregate away noise and have clearer causal relationships [SRC-46][SRC-55][SRC-77]
3. **Defensive impact remains the most challenging aspect to quantify**, with box-score-based defensive metrics (DBPM, defensive Win Shares) showing only 50-60% reliability [SRC-47][SRC-50][SRC-54]
4. **Multi-year data substantially improves reliability**: RAPM standard errors decrease ~80% when using 3+ years vs. single-season data [SRC-40]
5. **Kalman filtering (DARKO) and luck adjustment (PIPM, LEBRON) represent cutting-edge approaches** to reducing noise and capturing true impact [SRC-109][SRC-111][SRC-124][SRC-126]
6. **PER, DBPM, and APM should be excluded or heavily downweighted in ML models** due to poor defensive capture, outdated constants, or instability [SRC-16][SRC-30][SRC-54][SRC-67][SRC-89][SRC-92]
7. **Projection systems (CARMELO) answer different questions than impact metrics** and should not be used interchangeably [SRC-97][SRC-137]

---

## References

All sources are documented in `nba_metrics_sources.md` with full URLs and descriptions.