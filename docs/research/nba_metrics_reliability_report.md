# NBA Advanced Metrics: Grouped by Reliability

This report categorizes NBA advanced metrics by their reliability at capturing true player and team impact, with detailed justification for each classification.

---

## Tier 1: High Reliability (85-95%)

These metrics use large sample sizes, control for context (teammates, opponents, pace), and have been validated through out-of-sample testing or strong correlation with team success.

### EPM (Estimated Plus-Minus)

**Reliability Score:** 85-90% [SRC-39]

**Why This Rating:**

1. **Methodology:** Combines Estimated Skills (optimized, decay-weighted career stats accounting for stat stabilization rates) with multi-year RAPM using Bayesian priors [SRC-36][SRC-71]
2. **Data Sources:** Incorporates box score, play-by-play, and tracking data [SRC-36][SRC-39]
3. **Validation:** Validated through out-of-sample testing against future RAPM [SRC-39]
4. **Comparative Performance:** Consistently outperforms other metrics in head-to-head comparisons [SRC-37][SRC-39]

**Evidence:**

- EPM and RPM (similar methodology) were the only metrics using RAPM directly with Bayesian priors that consistently performed best among all metrics, with EPM taking the lead overall [SRC-37]
- Team EPM ratings predict game margins with RMSE of 12.1 points, better than traditional SRS [SRC-36]

**Caveats:**

- Full methodology not publicly documented, limiting independent reproducibility [SRC-39]

---

### DARKO (Daily Adjusted and Regressed Kalman Optimized)

**Reliability Score:** 85-90% [SRC-111][SRC-124]

**Why This Rating:**

1. **Methodology:** Uses Kalman filtering to update player estimates game-by-game, with exponential decay for older games [SRC-111][SRC-124][SRC-133]
2. **Innovation:** Unlike other metrics that reset each season, DARKO treats every game as an event and continuously updates [SRC-124]
3. **Validation:** Used in peer-reviewed academic research (Wharton, 2023) as "the most predictive all-in-one skill metric for NBA players" [SRC-111]
4. **Recency Weighting:** Recent games are weighted more heavily than older games (e.g., game 20 days ago is discounted less than game 40 days ago) [SRC-124][SRC-133]

**Evidence:**

- DARKO is used in academic research as the most predictive public metric for player skill [SRC-111]
- Kalman filtering optimally balances prior beliefs with new data, improving stability [SRC-109][SRC-111]

**Caveats:**

- Full methodology not completely public [SRC-111]
- Relies on RAPM family inputs, so inherits some RAPM limitations [SRC-118][SRC-123]

---

### Net Rating

**Reliability Score:** 90-95% [SRC-55][SRC-77]

**Why This Rating:**

1. **Methodology:** Simple, transparent formula (ORtg - DRtg) that directly measures point differential per 100 possessions [SRC-55][SRC-77]
2. **Predictive Power:** The single most predictive metric for NBA team quality [SRC-55][SRC-77]
3. **Noise Level:** Controls for pace and has minimal noise

**Evidence:**

- Net Rating is described as "the single most predictive metric for NBA team quality" [SRC-55][SRC-77]

**Caveats:**

- Team-level only; does not identify which players drive the differential [SRC-55][SRC-77]

---

### Team PIE

**Reliability Score:** R² = 0.908 with winning percentage [SRC-1]

**Why This Rating:**

1. **Methodology:** Captures percentage of all game events (positive and negative) achieved by a team [SRC-1][SRC-6]
2. **Correlation:** Highly correlated with winning [SRC-1][SRC-6]
3. **Transparency:** Simple, transparent formula with no black-box components

**Evidence:**

- NBA Stats reports R² of 0.908 between team PIE and winning percentage, indicating "strong" correlation [SRC-1]

**Caveats:**

- Does not adjust for opponent quality [SRC-1]

---

### Pace

**Reliability Score:** 95%+ [SRC-15]

**Why This Rating:**

1. **Methodology:** Direct count of possessions per 48 minutes; formula is straightforward and based on observable events (FGA, FTA, TOV) [SRC-2][SRC-15]
2. **Estimation Error:** Minimal estimation error

**Evidence:**

- Pace is a direct counting stat with well-established formula; average NBA pace is ~94 possessions, with clear differentiation between fast (Houston ~99) and slow (NYK ~92.5) teams [SRC-15]

**Caveats:**

- Does not capture quality of possessions [SRC-15]

---

### Four Factors (Aggregate)

**Reliability Score:** ~95% of variance explained [SRC-46][SRC-77]

**Why This Rating:**

1. **Methodology:** Dean Oliver's Four Factors (eFG%, TOV%, OREB%, FTR) collectively explain ~95% of variance in offensive efficiency [SRC-46][SRC-77]
2. **Comprehensiveness:** Each factor captures a distinct, measurable aspect of team performance
3. **Validation:** 2023 arXiv paper mathematically demonstrates the relationship between Four Factors and efficiency ratings [SRC-46]

**Evidence:**

- Research shows the Four Factors explain approximately 95% of variance in offensive efficiency [SRC-77]
- A 2023 arXiv paper mathematically demonstrates the relationship between Four Factors and efficiency ratings [SRC-46]

**Caveats:**

- Weights (40/25/20/15) are approximations and may vary by era/team [SRC-46][SRC-75]

---

## Tier 2: Moderate-High Reliability (75-85%)

These metrics are well-validated but have notable limitations (e.g., box score only, defensive estimation issues, or moderate sample size requirements).

### RAPM (Regularized Adjusted Plus-Minus)

**Reliability Score:** 80-85% [SRC-43][SRC-67]

**Why This Rating:**

1. **Methodology:** Controls for teammate/opponent quality via ridge regression on lineup data [SRC-34][SRC-44]
2. **Stability:** Standard errors decrease ~80% with multi-year vs. single-season data [SRC-40][SRC-43]
3. **Recognition:** Regarded as one of the most comprehensive single-number metrics [SRC-43][SRC-44]
4. **Uncertainty Quantification:** Standard errors and confidence intervals can be computed [SRC-73]

**Evidence:**

- RAPM correlation with team wins is 81.9% [SRC-67]
- Standard errors for multiyear RAPM are substantially lower, making ratings "far more reliable" [SRC-40]
- Confidence intervals can be computed (e.g., Kyle Korver's 95% CI: [-1.21, 4.16]) [SRC-73]

**Caveats:**

- Still noisy for low-minute players [SRC-34][SRC-38][SRC-43]
- Assumes linearity (no interaction effects between players) [SRC-34][SRC-38][SRC-43]
- Cannot capture non-scoring impact (e.g., spacing, gravity) [SRC-34][SRC-38][SRC-43]

---

### PIPM (Player Impact Plus-Minus)

**Reliability Score:** 80-85% [SRC-90][SRC-113]

**Why This Rating:**

1. **Methodology:** Combines box-score prior (15-year RAPM regression) with luck-adjusted on/off data [SRC-90][SRC-113][SRC-127]
2. **Luck Adjustment:** Removes variance from opponent 3P%, FT%, rebounding luck, and turnover variance—factors outside player control [SRC-126][SRC-127]
3. **Validation:** R² = 0.875 with 15-year RAPM sample [SRC-113]
4. **Recognition:** Described as "one of the most accurate publicly available impact metrics in terms of predicting future results" [SRC-90]

**Evidence:**

- Luck-adjusted methodology uses mean regression for Four Factors components to estimate what team efficiency should be without variance from uncontrollable stats [SRC-127][SRC-128]
- PIPM combines box score stability with on/off context, providing a clearer view of process rather than just results [SRC-126][SRC-129]

**Caveats:**

- Still subject to on/off noise for low-minute players [SRC-113][SRC-118]
- Box-score prior inherits BPM's defensive limitations [SRC-113][SRC-118]

---

### RPM / LEBRON / RAPTOR

**Reliability Score:** 80-85% [SRC-37][SRC-67][SRC-81]

**Why This Rating:**

1. **Methodology:** All combine box score priors with RAPM or on/off data, stabilizing estimates while incorporating additional context [SRC-37][SRC-78][SRC-80][SRC-87]
2. **Additional Features:**
   - RAPTOR: Incorporates tracking data [SRC-80][SRC-81][SRC-87]
   - LEBRON: Includes luck adjustment (removes variance from opponent 3P%) [SRC-78][SRC-82][SRC-83]

**Evidence:**

- RPM correlation with team wins is 81.9% [SRC-67]
- RAPTOR's box-score-only version correlates 0.890 overall with full tracking-based version [SRC-81]

**Caveats:**

- Methodologies not fully public [SRC-37][SRC-80][SRC-87]
- Subject to RAPM limitations [SRC-37][SRC-80][SRC-87]

---

### Win Shares (WS/48)

**Reliability Score:** 75-80% (WS/48: 83.1% correlation with wins) [SRC-21][SRC-67]

**Why This Rating:**

1. **Methodology:** Directly tied to team wins (one WS ≈ one win) [SRC-17][SRC-18]
2. **Validation:** Average absolute error of 2.72 wins when predicting team record [SRC-21]
3. **Correlation:** WS/48 correlates 83.1% with team wins [SRC-67]

**Evidence:**

- Basketball Reference reports average absolute error of 2.72 wins [SRC-21]
- Four-year study shows WS/48 correlation of 83.1% with wins [SRC-67]

**Caveats:**

- Defensive Win Shares are problematic; assumes equal defensive contribution then adjusts via box score, undervaluing elite defenders [SRC-17][SRC-50][SRC-64]

---

### BPM (Total)

**Reliability Score:** 70-75% (79.1% correlation with wins) [SRC-47][SRC-67]

**Why This Rating:**

1. **Methodology:** Position-aware regression on RAPM basis; excellent for offense [SRC-47]
2. **Correlation:** Correlates 79.1% with team wins [SRC-67]
3. **Transparency:** Developer (Daniel Myers) explicitly acknowledges limitations [SRC-47]

**Evidence:**

- Four-year study shows BPM correlation of 79.1% with wins [SRC-67]
- Myers explicitly states BPM is "good at measuring offense" but DBPM should be viewed skeptically [SRC-47]

**Caveats:**

- DBPM is unreliable (~50-60%); box score cannot capture positioning, communication, or other defensive elements [SRC-47][SRC-54]

---

### True Shooting (TS%)

**Reliability Score:** 75-80% [SRC-10]

**Why This Rating:**

1. **Methodology:** Accounts for 2PT, 3PT, and FT in a single efficiency metric; formula is transparent and widely validated [SRC-2][SRC-10]

**Evidence:**

- TS% is described as a more accurate measure of shooting efficiency than FG% [SRC-2][SRC-10]

**Caveats:**

- Does not account for shot difficulty, context, or playmaking impact [SRC-10]

---

### Defensive Rating (DRtg) / Offensive Rating (ORtg)

**Reliability Score:** 85-90% [SRC-55][SRC-77]

**Why This Rating:**

1. **Methodology:** Direct measure of points allowed/scored per 100 possessions; controls for pace [SRC-55][SRC-77]

**Evidence:**

- Elite NBA defenses hold opponents below 108 DRtg; ORtg/DRtg are foundational team metrics [SRC-55][SRC-77]

**Caveats:**

- Individual DRtg is noisy; team-level is more reliable [SRC-55][SRC-77]

---

## Tier 3: Moderate Reliability (60-75%)

These metrics provide useful information but have significant limitations (e.g., outdated constants, poor defensive capture, or moderate correlation with wins).

### PIE (Player)

**Reliability Score:** 70-75% [SRC-1][SRC-6]

**Why This Rating:**

1. **Methodology:** Simple, transparent formula capturing percentage of game events [SRC-1][SRC-6]
2. **Correlation:** Correlates strongly with team winning (R² = 0.908) but does not adjust for pace or opponent quality [SRC-1][SRC-6]

**Evidence:**

- NBA Stats reports R² of 0.908 between team PIE and winning percentage [SRC-1]

**Caveats:**

- Does not adjust for pace, opponent quality, or event impact (all events weighted equally) [SRC-1][SRC-6]

---

### Rebound Percentage (REB%, ORB%, DRB%)

**Reliability Score:** 75-80% [SRC-76]

**Why This Rating:**

1. **Methodology:** Controls for team context (percentage of available rebounds grabbed) rather than raw totals [SRC-15][SRC-76]

**Evidence:**

- Rebound percentages are standard advanced stats used to evaluate rebounding impact [SRC-15][SRC-76]

**Caveats:**

- Does not capture rebounding difficulty (contested vs. uncontested) or boxing out impact [SRC-76]

---

### Assist Percentage (AST%)

**Reliability Score:** 70-75% [SRC-76]

**Why This Rating:**

1. **Methodology:** Measures percentage of teammate baskets assisted while player is on court; controls for team context [SRC-15][SRC-76]

**Evidence:**

- AST% is a standard advanced stat for evaluating playmaking [SRC-15][SRC-76]

**Caveats:**

- Does not capture pass quality, shot creation, or gravity effects [SRC-76]

---

### TPA (Total Points Added)

**Reliability Score:** 70-75% [SRC-108]

**Why This Rating:**

1. **Methodology:** Cumulative transformation of BPM (TPA ≈ BPM × minutes played) [SRC-108][SRC-122]
2. **Inherits BPM's Reliability:** Same strengths and weaknesses as BPM [SRC-108]

**Evidence:**

- Reddit discussion notes "TPA is just BPM times minutes played" [SRC-108]
- TPA formula: OPA + DPS = OBPM × possessions + DBPM × possessions [SRC-121][SRC-122]

**Caveats:**

- Inherits all of BPM's limitations, especially DBPM's poor defensive capture [SRC-47][SRC-54][SRC-108]
- Cumulative stats conflate quality and quantity [SRC-108]
- Not a distinct metric; merely a transformation of BPM [SRC-108]

---

## Tier 4: Low-Moderate Reliability (50-65%)

These metrics have notable flaws that limit their ability to capture true impact, particularly on defense or for non-box-score contributions.

### PER (Player Efficiency Rating)

**Reliability Score:** 50-60% [SRC-30][SRC-67]

**Why This Rating:**

1. **Correlation:** Correlates only 67.5% with team wins—lowest among major all-in-one metrics [SRC-67]
2. **Developer Admission:** Hollinger admits PER is not reliable for defense (only incorporates STL/BLK) [SRC-16][SRC-30]
3. **Outdated Constants:** Constants like 0.44 (for possession estimation) may not reflect modern NBA [SRC-30]
4. **Volume Bias:** Favors volume over efficiency and does not account for teammate/opponent quality [SRC-23][SRC-29][SRC-30]

**Evidence:**

- Four-year study shows PER correlation of 67.5% with wins—lowest among WS/48 (83.1%), RPM (81.9%), Rtg (81.5%), BPM (79.1%), WS (76.9%), VORP (75.3%) [SRC-67]
- Hollinger freely admits PER is not a reliable measure of defensive acumen [SRC-16][SRC-30]

**Caveats:**

- Severely undervalues defense; overweights offensive volume; outdated constants; no context adjustment [SRC-16][SRC-23][SRC-29][SRC-30]

---

### DBPM (Defensive Box Plus/Minus)

**Reliability Score:** 50-60% [SRC-47][SRC-54]

**Why This Rating:**

1. **Methodology:** Derived as Total BPM - OBPM; inherits all box score defensive limitations (only STL, BLK, DRB) [SRC-47][SRC-54]
2. **Developer Skepticism:** Myers explicitly states DBPM should be viewed skeptically [SRC-47][SRC-54]

**Evidence:**

- Reddit discussion notes "DBPM has significant flaws, and even its creator has reportedly expressed skepticism about its validity" [SRC-54]
- Myers states "take DBPM with a spoonful of salt" [SRC-47]

**Caveats:**

- Box score cannot capture positioning, communication, switchability, or other critical defensive elements [SRC-47][SRC-54]

---

### APM (Adjusted Plus-Minus)

**Reliability Score:** 50-60% [SRC-89][SRC-92]

**Why This Rating:**

1. **Methodology:** Uses ordinary least squares (OLS) regression on lineup data without regularization [SRC-88][SRC-91]
2. **Critical Flaw:** Severe multicollinearity makes APM unstable—even multi-year samples produce unreliable estimates [SRC-89][SRC-92]
3. **Sample Size Requirements:** Requires thousands of games to achieve stability [SRC-91][SRC-92]
4. **Superseded:** RAPM applies ridge regression to solve multicollinearity, making APM primarily of historical interest [SRC-34][SRC-89][SRC-94]

**Evidence:**

- "Pure APM, though, is unstable even in multi year samples due to the collinearity" [SRC-92]
- "Sill (2010) introduced the regularized version of the APM model (RAPM) that has more predictive power" [SRC-89]

**Caveats:**

- Superseded by RAPM; should not be used for modern player evaluation [SRC-34][SRC-89][SRC-94]
- Foundation for modern plus-minus metrics, but impractical for actual use [SRC-88][SRC-91]

---

### Usage Rate (USG%)

**Reliability Score:** 65-70% [SRC-11]

**Why This Rating:**

1. **Methodology:** Measures percentage of team possessions used by player, but does not account for efficiency or context [SRC-11][SRC-15]

**Evidence:**

- USG% is a standard advanced stat but is descriptive rather than evaluative [SRC-11][SRC-15]

**Caveats:**

- High usage does not imply high impact; does not account for efficiency or playmaking gravity [SRC-11]

---

## Projection Systems (Not Directly Comparable)

### CARMELO (Career-Arc Regression Model Estimator with Local Optimization)

**Reliability Score:** N/A (projection system, not single-season impact metric) [SRC-97][SRC-137]

**Why Not Rated:**

- CARMELO forecasts **future career trajectories** (WARP), not current-season impact [SRC-97][SRC-102][SRC-135]
- Answers a fundamentally different question than impact metrics like EPM, RAPM, BPM [SRC-97][SRC-137]
- Discontinued by FiveThirtyEight (~2020), replaced by RAPTOR [SRC-80][SRC-87]

**Evidence:**

- "CARMELO ultimately is just a WAR projection system" [SRC-137]
- Used in FiveThirtyEight's CARM-Elo team projection system, which performed well against Vegas spreads [SRC-96][SRC-110]

**Caveats:**

- Not comparable to single-season impact metrics [SRC-97][SRC-137]
- Relies on RPM (discontinued) and BPM (box-score-only defense) [SRC-99][SRC-105]

---

## Source Mapping

All citations reference source IDs (SRC-X) that correspond to entries in `nba_metrics_sources.md`.