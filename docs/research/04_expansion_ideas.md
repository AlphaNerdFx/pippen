# NBA Player Impact ML Model: Expansion Ideas

## Executive Summary

This document provides ideas for expanding the scope of the NBA player impact ML model to match existing FOSS (Free and Open-Source Software) applications like DARKO, CARMELO, and SportsDataverse.

**Current Scope:**
- Individual player impact estimation (EPM, RAPM, DARKO-style)
- Team-level aggregation (Net Rating, Four Factors)
- Historical analysis (season-by-season impact)

**Expansion Goals:**
- Real-time game projections (match DARKO)
- Lineup optimization & swap analysis (match L-RAPM)
- Career trajectory projections (match CARMELO)
- Tracking data integration (match EPM/RAPTOR)
- Team analytics dashboard (match SportsDataverse)
- Open-source Python package (match SportsDataverse ecosystem)

---

## Expansion Idea 1: Real-Time Game Projections (Match DARKO)

**What DARKO Does:**

- Provides **daily updating projections** for every player, every game [SRC-174]
- Combines player impact (DPM) with **minutes projections** to estimate per-game impact [SRC-174]
- Generates **point spread projections** by summing player impacts + home court + team-level statistics [SRC-174]
- Updates projections **for every box-score and impact stat, for every day of the season** [SRC-174]

**How to Expand:**

1. **Minutes Projection Model:**
   - Train model to predict player minutes based on:
     - Historical minutes (rolling averages, exponential decay)
     - Role (starter, bench, situational)
     - Matchup (opponent strength, pace)
     - Rest (days since last game, back-to-back indicator)
   - Use gradient boosting or neural networks for non-linear patterns

2. **Game-Level Impact Estimation:**
   - For each game, compute:
     ```
     Player Game Impact = Player DPM × Projected Minutes / 48
     Team Projected Margin = Σ(Player Game Impact) + Home Court + Team-Level Adjustments
     ```
   - Blend with team-level statistics (like DARKO) to stabilize ratings [SRC-174]

3. **Real-Time Updates:**
   - Update projections after every game (daily batch updates)
   - Incorporate in-game data for live projections (optional, more complex)

**FOSS Reference:**

- **DARKO:** Daily updating projections, DPM, minutes projections, point spreads [SRC-174]
- **nba-sql:** Open-source NBA database (MariaDB/MySQL, Postgres, SQLite) [SRC-159][SRC-167]

---

## Expansion Idea 2: Lineup Optimization & Swap Analysis

**What It Does:**

- Answer "what-if" questions: "What if Team X swaps Player A for Player B?"
- Estimate impact of lineup changes on team Net Rating
- Identify optimal lineups based on player compatibility

**How to Implement:**

1. **Lineup RAPM (L-RAPM):**
   - Extend RAPM to estimate **lineup-level** impact (not just individual players) [SRC-35]
   - Use ridge regression on lineup stints to estimate 5-player combination effects [SRC-35]

2. **Player Compatibility Metrics:**
   - Compute **pairwise synergy scores** (how well two players perform together vs. apart)
   - Use on/off data to estimate net impact of player combinations

3. **Swap Analysis:**
   - For proposed swap (Player A → Player B):
     ```
     Projected Δ Net Rating = (Player B RAPM - Player A RAPM) + Lineup Adjustment
     ```
   - Account for role fit, playing style compatibility, defensive scheme fit

**FOSS Reference:**

- **L-RAPM (Lineup RAPM):** arXiv paper on lineup-level RAPM [SRC-35]
- **hoopR:** R package for play-by-play data (can extract lineup data) [SRC-162]

---

## Expansion Idea 3: Career Trajectory Projections (Match CARMELO)

**What CARMELO Does:**

- Forecasts **player career trajectories** in WARP (Wins Above Replacement) [SRC-97][SRC-102]
- Uses **historical comparables** (similar players from NBA history) to project future [SRC-97][SRC-104]
- Inputs: RPM (2/3) + BPM (1/3) + scouting data (for draft prospects) [SRC-99][SRC-132]
- Outputs: Season-by-season WARP projections, summed to estimate total career value [SRC-105][SRC-132]

**How to Expand:**

1. **Historical Comparables Engine:**
   - Build database of historical player seasons (1998-99 to present)
   - For current player, find similar players based on:
     - Age, position, physical attributes
     - Skill profile (shooting, playmaking, defense)
     - Career trajectory to date

2. **Trajectory Modeling:**
   - Use **Gaussian Process Regression** or **Bayesian Hierarchical Models** to model career arcs
   - Estimate peak age, decline rate, career length distribution

3. **WARP Calculation:**
   - Convert player impact (EPM/RAPM) to wins using:
     ```
     WARP = (Player Impact - Replacement Level) × Minutes / 48 × Games / 82
     ```
   - Replacement level ≈ -2.0 EPM (typical replacement player)

4. **Probabilistic Forecasts:**
   - Generate **probability distributions** for future WARP (not just point estimates)
   - Show uncertainty bands (e.g., 10th-90th percentile range)

**FOSS Reference:**

- **CARMELO:** FiveThirtyEight's career projection system [SRC-97][SRC-99][SRC-106]
- **ncaahoopR:** R package for college basketball data (for draft prospect projections) [SRC-166]

---

## Expansion Idea 4: Tracking Data Integration (Match EPM/RAPTOR)

**What EPM/RAPTOR Do:**

- Incorporate **player tracking data** (since 2013-14) for richer feature set [SRC-36][SRC-80][SRC-87]
- Track metrics:
  - **Contested shots:** Shots defended within X feet
  - **Defensive positioning:** Distance to nearest offensive player
  - **Screen setting:** Number and quality of screens
  - **Spacing:** Floor spacing, gravity effects

**How to Expand:**

1. **Data Sources:**
   - **NBA.com Tracking Data:** Available via API (since 2013-14)
   - **pbpstats.com:** Enhanced tracking data (used by DARKO) [SRC-174]
   - **Second Spectrum:** Official NBA tracking data provider (licensed)

2. **Feature Engineering:**
   - **Offensive Tracking Features:**
     - Catch-and-shoot efficiency
     - Pull-up shooting efficiency
     - Rim finishing rate and efficiency
     - Passing metrics (potential assists, secondary assists)
   - **Defensive Tracking Features:**
     - Contest rate (percentage of shots contested)
     - Deflections, charges drawn
     - Switch rate, closeout speed

3. **Model Integration:**
   - Add tracking features to existing model (EPM/RAPM-style)
   - Use gradient boosting or neural networks to capture non-linear tracking effects

**FOSS Reference:**

- **EPM:** Incorporates tracking data in Estimated Skills [SRC-36]
- **RAPTOR:** Uses tracking data, height, age, draft position [SRC-80][SRC-87]
- **BasketTracking:** Computer vision + deep learning for action tracking [SRC-160]

---

## Expansion Idea 5: Team-Level Analytics Dashboard

**What It Does:**

- Provide **team-level analytics** (Net Rating, Four Factors, lineup data)
- Visualize team performance over time
- Compare teams across seasons

**How to Implement:**

1. **Team Metrics:**
   - Net Rating (ORtg - DRtg) [SRC-55][SRC-77]
   - Four Factors (eFG%, TOV%, OREB%, FTR) [SRC-46][SRC-49]
   - Lineup Net Ratings (top/bottom 5-player combinations)

2. **Visualization:**
   - Use **Plotly Dash** or **Streamlit** for interactive dashboards
   - Show time-series trends (Net Rating over season)
   - Compare teams side-by-side

3. **Data Pipeline:**
   - Ingest team-level data daily (NBA.com API)
   - Compute metrics automatically
   - Update dashboard in real-time

**FOSS Reference:**

- **nba-sql:** NBA database with team-level data [SRC-159][SRC-167]
- **SportsDataverse:** Family of 26 open-source packages (R, Python, Node.js) [SRC-168]
- **hoopR:** R package for men's basketball play-by-play data [SRC-162]

---

## Expansion Idea 6: Open-Source Package (Match SportsDataverse)

**What SportsDataverse Does:**

- Provides **open-source packages** in R, Python, and Node.js [SRC-168]
- Offers **clean play-by-play data** and models anyone can use [SRC-168]
- Maintained by community contributors across sports analytics [SRC-168]

**How to Expand:**

1. **Python Package:**
   - Create `nba-impact` package on PyPI
   - Functions:
     - `fetch_player_data()`: Download box scores, play-by-play
     - `compute_rapm()`: Calculate RAPM from lineup data
     - `compute_epm()`: Calculate EPM-style metrics
     - `project_player_impact()`: Predict future impact
   - Include pre-trained models (EPM, RAPM, DARKO-style)

2. **Documentation:**
   - Comprehensive docs (ReadTheDocs or MkDocs)
   - Tutorials (Jupyter notebooks)
   - API reference

3. **Community:**
   - Open-source on GitHub
   - Encourage contributions (feature requests, bug fixes)
   - Regular releases (monthly or quarterly)

**FOSS Reference:**

- **SportsDataverse:** 26 open-source packages, community-maintained [SRC-168]
- **hoopR:** R package for basketball data [SRC-162]
- **nba-sql:** Open-source NBA database [SRC-159][SRC-167]

---

## Implementation Roadmap

### Phase 1: Foundation (Months 1-3)

**Goals:**
- Build data ingestion pipeline (NBA.com API, pbpstats.com)
- Implement RAPM calculation (ridge regression)
- Train initial model (EPM-style, using box-score + RAPM)
- Deploy MVP (FastAPI + Docker on single VM)

**Deliverables:**
- Data pipeline (Airflow/Prefect)
- RAPM calculation script
- Trained model (XGBoost or ridge regression)
- Deployed API endpoint

---

### Phase 2: Enhancement (Months 4-6)

**Goals:**
- Integrate tracking data (since 2013-14)
- Implement DARKO-style daily updates (exponential decay)
- Add model interpretability (SHAP, LIME)
- Deploy to Kubernetes (KServe)

**Deliverables:**
- Tracking data features
- Daily updating model (DARKO-style)
- SHAP/LIME explanations
- Kubernetes deployment

---

### Phase 3: Expansion (Months 7-12)

**Goals:**
- Implement lineup optimization (L-RAPM)
- Add career trajectory projections (CARMELO-style)
- Build team analytics dashboard (Plotly Dash/Streamlit)
- Release open-source Python package

**Deliverables:**
- Lineup RAPM model
- Career projection system
- Team dashboard
- `nba-impact` Python package on PyPI

---

### Phase 4: Production Hardening (Months 13-18)

**Goals:**
- Implement automated drift detection (Evidently AI)
- Set up CI/CD pipeline (GitHub Actions)
- Add monitoring/alerting (MLflow + Prometheus/Grafana)
- Scale to handle production traffic

**Deliverables:**
- Drift detection pipeline
- CI/CD automation
- Monitoring dashboard
- Production-grade deployment

---

## References

| ID | Title | URL | Key Claims Supported |
|----|-------|-----|---------------------|
| SRC-35 | Lineup Regularized Adjusted Plus-Minus | https://arxiv.org/abs/2601.15000 | L-RAPM methodology |
| SRC-36 | About Estimated Plus-Minus | https://dunksandthrees.com/about/epm | EPM tracking data |
| SRC-46 | Dean Oliver's Four Factors Revisited | https://arxiv.org/abs/2305.13032 | Four Factors |
| SRC-49 | NBA Advanced Stats: Four Factors | https://hoopshabit.com/2014/07/23/nba-advanced-stats-four-factors-winning/ | Four Factors weights |
| SRC-55 | Basketball Advanced Analytics Betting | https://basketballbetstrategy.com/articles/basketball-advanced-analytics-betting/ | Net Rating |
| SRC-77 | Basketball Analytics for Betting | https://betmana.co.uk/guide/basketball-analytics-for-betting/ | Four Factors, Net Rating |
| SRC-80 | Is Lebron Still A Dominating... | https://fivethirtyeight.com/features/winners-and-losers-in-our-updated-nba-season-predictions/ | RAPTOR tracking |
| SRC-87 | RAPTOR Explained | https://www.nbastuffer.com/analytics101/raptor/ | RAPTOR methodology |
| SRC-97 | We're Predicting The Career Of Every NBA Player | https://fivethirtyeight.com/features/how-were-predicting-nba-player-career/ | CARMELO |
| SRC-99 | What's New In Our NBA Player Projections | https://fivethirtyeight.com/features/whats-new-in-our-nba-player-projections-for-2017-18/ | CARMELO RPM+BPM |
| SRC-105 | Our NBA Player Projections Are Ready | https://fivethirtyeight.com/features/our-nba-player-projections-are-ready-for-2018-19/ | CARMELO WARP |
| SRC-106 | CARMELO Explained | https://www.nbastuffer.com/analytics101/carmelo/ | CARMELO methodology |
| SRC-132 | The Top 50 NBA Draft Prospects | https://fivethirtyeight.com/features/the-top-50-nba-draft-prospects-according-to-our-carmelo-projections/ | CARMELO draft projections |
| SRC-159 | GitHub - NBA Analytics | https://github.com/topics/nba-analytics | nba-sql |
| SRC-160 | GitHub - BasketTracking | https://github.com/Basket-Analytics/BasketTracking | Basketball tracking |
| SRC-162 | GitHub - hoopR | https://github.com/sportsdataverse/hoopR | Basketball play-by-play |
| SRC-166 | Top 17 Basketball Open-Source Projects | https://www.libhunt.com/topic/basketball | ncaahoopR |
| SRC-167 | Top 23 Sports-Analytic Open-Source Projects | https://www.libhunt.com/topic/sports-analytics | Sports analytics FOSS |
| SRC-168 | About - SportsDataverse | https://www.sportsdataverse.org/about | SportsDataverse packages |
| SRC-174 | Introducing DARKO | https://www.nytimes.com/athletic/2613015/2021/05/26/introducing-darko-an-nba-playoffs-game-projection-and-betting-guide/ | DARKO projections |