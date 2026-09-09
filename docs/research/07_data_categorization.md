# NBA Player Impact ML Model: Data Categorization Framework

## Executive Summary

This document provides a framework for categorically splitting NBA data based on the project's requirements, including categorization by metric reliability tier, data type, temporal granularity, and target variable alignment.

---

## Part 1: By Metric Reliability Tier (Primary Categorization)

Based on the reliability analysis from the main reports, categorize data sources by the reliability tier of metrics they provide:

### 1.1 Tier 1 Data (High Reliability, 85-95%)

**Sources:**
- **NBA API (tracking data endpoints):** EPM-style tracking features (contested shots, defensive positioning) [SRC-197][SRC-207]
- **NBA API (box scores + play-by-play):** RAPM calculation (lineup stints, scoring margin) [SRC-214][SRC-220]
- **DARKO API (if available):** Daily DPM projections [SRC-174][SRC-219]

**Specific Data:**
- Player tracking metrics (contested shots, speed, distance) [SRC-197]
- Play-by-play data for RAPM stint extraction [SRC-214][SRC-220]
- Team Net Rating (ORtg - DRtg) [SRC-55][SRC-77]
- Four Factors (eFG%, TOV%, OREB%, FTR) [SRC-46][SRC-49]

**Use Cases:**
- Primary target variables (EPM, DARKO/DPM, RAPM) [SRC-36][SRC-111]
- High-reliability features for model training [SRC-34][SRC-44]

---

### 1.2 Tier 2 Data (Moderate-High Reliability, 75-85%)

**Sources:**
- **Basketball-Reference:** Win Shares, BPM (pre-computed) [SRC-198][SRC-207]
- **NBA API (advanced stats endpoints):** PIPM, RPM (if available) [SRC-90][SRC-113]

**Specific Data:**
- Win Shares (Offensive WS, Defensive WS, WS/48) [SRC-17][SRC-21]
- BPM (OBPM, DBPM, Total BPM) [SRC-47][SRC-52]
- PIPM (O-PIPM, D-PIPM, Total PIPM) [SRC-90][SRC-113]
- TS%, AST%, REB% [SRC-10][SRC-15]

**Use Cases:**
- Secondary features for model training [SRC-47][SRC-67]
- Validation targets (compare model predictions to WS/BPM) [SRC-21][SRC-67]

---

### 1.3 Tier 3 Data (Moderate Reliability, 60-75%)

**Sources:**
- **NBA API (traditional stats endpoints):** PER, PIE, USG% [SRC-1][SRC-6]
- **Basketball-Reference:** PER, PIE (pre-computed) [SRC-198]

**Specific Data:**
- PER (Player Efficiency Rating) [SRC-16][SRC-26]
- PIE (Player Impact Estimate) [SRC-1][SRC-6]
- USG% (Usage Rate) [SRC-11][SRC-15]
- REB%, AST% [SRC-15][SRC-76]

**Use Cases:**
- Tertiary features (downweight in model) [SRC-16][SRC-30]
- Descriptive analysis (not primary targets) [SRC-1][SRC-6]

---

### 1.4 Tier 4 Data (Low-Moderate Reliability, 50-65%)

**Sources:**
- **Basketball-Reference:** DBPM (Defensive BPM) [SRC-54][SRC-198]
- **Historical APM calculations** (if available) [SRC-89][SRC-92]

**Specific Data:**
- DBPM (Defensive Box Plus/Minus) [SRC-47][SRC-54]
- APM (Adjusted Plus-Minus, unregularized) [SRC-88][SRC-91]

**Use Cases:**
- Exclude or heavily downweight in model [SRC-47][SRC-89]
- Historical comparison only (not for training) [SRC-89][SRC-92]

---

## Part 2: By Data Type (Secondary Categorization)

### 2.1 Box Score Data

**Sources:**
- **NBA API:** `boxscoreplayerstats`, `boxscoresummary` [SRC-203][SRC-207]
- **SportsDataverse:** `load_nba_player_box()`, `load_nba_team_box()` [SRC-193]
- **Basketball-Reference:** Season totals, game logs [SRC-204][SRC-207]

**Specific Fields:**
- **Player:** PTS, REB, AST, STL, BLK, TOV, PF, FGM, FGA, 3PM, 3PA, FTM, FTA [SRC-4][SRC-12]
- **Team:** PTS, REB, AST, STL, BLK, TOV, PF, FGM, FGA, 3PM, 3PA, FTM, FTA [SRC-2][SRC-51]

**Use Cases:**
- Tier 2-3 features (BPM, WS, PER inputs) [SRC-47][SRC-67]
- Traditional box-score-based metrics [SRC-10][SRC-15]

**Temporal Granularity:**
- Game-level, season-level, career-level [SRC-193][SRC-203]

---

### 2.2 Play-by-Play Data

**Sources:**
- **NBA API:** `playbyplayv2`, `playbyplayv3` [SRC-207][SRC-220]
- **SportsDataverse:** `load_nba_pbp()` [SRC-193][SRC-194]
- **pbpstats.com:** Lineup-level play-by-play [SRC-198]

**Specific Fields:**
- Event type (shot, assist, turnover, foul, substitution) [SRC-214][SRC-215]
- Player IDs involved (shooter, assister, defender) [SRC-214]
- Timestamp (quarter, time remaining) [SRC-215]
- Shot location (X/Y coordinates, if available) [SRC-197][SRC-207]
- Lineup on court (5 players per team) [SRC-214][SRC-217]

**Use Cases:**
- RAPM stint extraction (lineup + scoring margin) [SRC-214][SRC-220]
- Possession-level analysis (Four Factors calculation) [SRC-46][SRC-77]
- Lineup optimization (L-RAPM) [SRC-35][SRC-217]

**Temporal Granularity:**
- Possession-level, event-level [SRC-214][SRC-215]

---

### 2.3 Tracking Data

**Sources:**
- **NBA API:** `dashv2`, `playerdashptshotlog` (aggregated tracking metrics) [SRC-197][SRC-207]
- **SportAPI Data:** Second Spectrum tracking (enterprise tier) [SRC-197]

**Specific Fields:**
- **Offensive:** Catch-and-shoot efficiency, pull-up shooting, rim finishing, passing metrics [SRC-197][SRC-207]
- **Defensive:** Contest rate, deflections, charges drawn, switch rate, closeout speed [SRC-197][SRC-207]
- **Physical:** Player position (X/Y), speed, distance traveled, touches [SRC-197]

**Use Cases:**
- EPM/RAPTOR-style tracking features [SRC-36][SRC-80]
- Defensive impact estimation (beyond box score) [SRC-47][SRC-54]
- Shot quality estimation (contested vs. uncontested) [SRC-197]

**Temporal Granularity:**
- Game-level, season-level (aggregated) [SRC-197][SRC-207]

---

### 2.4 Advanced Metrics (Pre-Computed)

**Sources:**
- **Basketball-Reference:** Win Shares, BPM, VORP, PER [SRC-198][SRC-207]
- **Dunks & Threes:** EPM (if API available) [SRC-36][SRC-218]
- **DARKO:** DPM (if API available) [SRC-174][SRC-219]

**Specific Fields:**
- **EPM:** O-EPM, D-EPM, Total EPM [SRC-36][SRC-39]
- **RAPM:** O-RAPM, D-RAPM, Total RAPM [SRC-34][SRC-44]
- **BPM:** OBPM, DBPM, Total BPM [SRC-47][SRC-52]
- **WS:** OWS, DWS, WS/48 [SRC-17][SRC-21]
- **PER, PIE, VORP** [SRC-16][SRC-67]

**Use Cases:**
- Target variables (EPM, RAPM, DARKO) [SRC-36][SRC-111]
- Validation targets (compare model predictions) [SRC-67]
- Feature inputs (for ensemble models) [SRC-47][SRC-67]

**Temporal Granularity:**
- Season-level, career-level [SRC-193][SRC-203]

---

## Part 3: By Temporal Granularity (Tertiary Categorization)

### 3.1 Game-Level Data

**Sources:**
- **NBA API:** Box scores, play-by-play [SRC-203][SRC-207]
- **SportsDataverse:** `load_nba_player_box()`, `load_nba_pbp()` [SRC-193]

**Specific Data:**
- Game box scores (player/team stats) [SRC-203]
- Play-by-play events [SRC-214]
- Game results (home/away, margin) [SRC-215]

**Use Cases:**
- DARKO-style daily updates (game-by-game impact) [SRC-124][SRC-174]
- Rolling averages (7-day, 30-day form) [SRC-174]
- Real-time projections (in-season) [SRC-174]

---

### 3.2 Season-Level Data

**Sources:**
- **NBA API:** `playercareerstats`, `teamyearbyyearstats` [SRC-203]
- **Basketball-Reference:** Season totals, advanced stats [SRC-204][SRC-207]
- **SportsDataverse:** `load_nba_player_stats()`, `load_nba_team_stats()` [SRC-193]

**Specific Data:**
- Season totals (PTS, REB, AST, etc.) [SRC-203]
- Advanced stats (PER, TS%, USG%) [SRC-1][SRC-16]
- Team stats (ORtg, DRtg, Four Factors) [SRC-2][SRC-51]

**Use Cases:**
- Primary training data (season-level EPM/RAPM targets) [SRC-36][SRC-44]
- Career trajectory modeling (age curves) [SRC-97][SRC-104]

---

### 3.3 Career-Level Data

**Sources:**
- **NBA API:** `playercareerstats` (full career) [SRC-203]
- **Basketball-Reference:** Career totals, per-game averages [SRC-204][SRC-207]

**Specific Data:**
- Career totals (PTS, REB, AST, etc.) [SRC-203]
- Career averages (PPG, RPG, APG) [SRC-203]
- Career advanced stats (PER, WS, BPM) [SRC-16][SRC-47]

**Use Cases:**
- CARMELO-style career projections [SRC-97][SRC-104]
- Historical comparables (find similar players) [SRC-97][SRC-132]

---

## Part 4: By Target Variable Alignment (Quaternary Categorization)

### 4.1 Primary Target Variables (Tier 1 Metrics)

**Data Required:**
- **EPM:** Box scores + play-by-play + tracking data (for Estimated Skills + RAPM) [SRC-36][SRC-71]
- **DARKO/DPM:** Box scores + play-by-play + minutes projections [SRC-111][SRC-174]
- **RAPM:** Play-by-play (lineup stints, scoring margin) [SRC-34][SRC-220]

**Sources:**
- **NBA API:** All required data (box scores, play-by-play, tracking) [SRC-203][SRC-207]
- **SportsDataverse:** Box scores + play-by-play (tidy format) [SRC-193][SRC-194]
- **pbpstats:** Lineup-level play-by-play [SRC-198]

**Preprocessing Steps:**
1. Extract lineup stints from play-by-play (5-player combinations) [SRC-214][SRC-220]
2. Calculate scoring margin per 100 possessions for each stint [SRC-220]
3. Apply ridge regression (RAPM) or Bayesian priors (EPM/DARKO) [SRC-34][SRC-44]

---

### 4.2 Secondary Target Variables (Tier 2 Metrics)

**Data Required:**
- **Win Shares:** Box scores + team ratings (offensive/defensive) [SRC-17][SRC-18]
- **BPM:** Box scores + position/role estimation [SRC-47][SRC-52]
- **PIPM:** Box scores + luck-adjusted on/off data [SRC-90][SRC-113]

**Sources:**
- **Basketball-Reference:** Pre-computed WS, BPM [SRC-198][SRC-207]
- **NBA API:** Box scores (for custom BPM calculation) [SRC-203]
- **BBall Index:** PIPM (if API available) [SRC-90][SRC-112]

**Preprocessing Steps:**
1. Calculate offensive/defensive ratings from box scores [SRC-17][SRC-55]
2. Apply Win Shares formula (OWS + DWS) [SRC-17][SRC-18]
3. For BPM, apply position-aware coefficients [SRC-47][SRC-52]

---

### 4.3 Validation Targets (Tier 3-4 Metrics)

**Data Required:**
- **PER:** Box scores (PTS, REB, AST, STL, BLK, TOV, PF, FGA, FTA) [SRC-16][SRC-26]
- **PIE:** Box scores (all game events) [SRC-1][SRC-6]
- **TS%, USG%:** Box scores (PTS, FGA, FTA, TOV) [SRC-10][SRC-15]

**Sources:**
- **NBA API:** Traditional stats endpoints [SRC-203]
- **Basketball-Reference:** Pre-computed PER, PIE, TS% [SRC-198]

**Use Cases:**
- Validate model predictions (correlation with PER, PIE) [SRC-67]
- Descriptive analysis (not primary targets) [SRC-1][SRC-16]

---

## References

| ID | Title | URL | Key Claims Supported |
|----|-------|-----|---------------------|
| SRC-1 | FAQ \| Stats \| NBA.com | https://www.nba.com/stats/help/faq | PIE formula, advanced stats |
| SRC-2 | Teams Advanced \| Stats | https://www.nba.com/stats/teams/advanced | Team advanced stats |
| SRC-4 | Basketball statistics - Wikipedia | https://en.wikipedia.org/wiki/Basketball_statistics | Basic stat abbreviations |
| SRC-6 | Basketball Stats Explained | https://www.sportsvisio.com/stories/basketball-stats-explained | PIE explanation |
| SRC-10 | Basketball Stats Explained | https://www.breakthroughbasketball.com/stats/definitions | TS% explanation |
| SRC-11 | Advanced NBA Stats for Dummies | https://bleacherreport.com/articles/1813902-advanced-nba-stats-for-dummies | USG% |
| SRC-12 | RealGM Stats Legend | https://basketball.realgm.com/info/glossary | Basic stat definitions |
| SRC-15 | Basic Advanced Stats Guide | https://www.reddit.com/r/nba/comments/1j5l0z/basic_advanced_stats_guide/ | Pace, AST%, REB%, USG% |
| SRC-16 | Player efficiency rating - Wikipedia | https://en.wikipedia.org/wiki/Player_efficiency_rating | PER formula |
| SRC-17 | Win Shares & Rookie Contracts | https://red.library.usd.edu/cgi/viewcontent.cgi?article=1013&context=honors-thesis | Win Shares formula |
| SRC-18 | Calculating Win Shares | https://www.sports-reference.com/cbb/about/ws.html | Win Shares calculation |
| SRC-21 | Blog Archive | https://www.basketball-reference.com/blog/index1c24.html?p=1858 | WS average absolute error |
| SRC-26 | The Ultimate PER Guide | https://www.cryptbeam.com/2022/05/11/the-ultimate-per-guide-untangling-john-hollingers-analytics-lovechild/ | PER formula breakdown |
| SRC-30 | Basketball, Stat: PER | https://www.reddit.com/r/nbadiscussion/comments/cmrr8x/basketball_stat_player_efficiency_rating_per/ | PER defense limitations |
| SRC-34 | Lineup Regularized Adjusted Plus-Minus | https://arxiv.org/abs/2601.15000 | RAPM methodology |
| SRC-35 | Lineup Regularized Adjusted Plus-Minus | https://arxiv.org/abs/2601.15000 | L-RAPM |
| SRC-36 | About Estimated Plus-Minus | https://dunksandthrees.com/about/epm | EPM methodology |
| SRC-39 | Estimated Plus-Minus - NBAstuffer | https://www.nbastuffer.com/analytics101/estimated-minus/ | EPM validation |
| SRC-44 | Regularized Adjusted Plus-Minus Calculator | https://metricgate.com/docs/regularized-adjusted-minus/ | RAPM ridge regression |
| SRC-46 | Dean Oliver's Four Factors Revisited | https://arxiv.org/abs/2305.13032 | Four Factors |
| SRC-47 | About Box Plus/Minus | https://www.basketball-reference.com/about/bpm2.html | BPM methodology |
| SRC-49 | NBA Advanced Stats: Four Factors | https://hoopshabit.com/2014/07/23/nba-advanced-stats-four-factors-winning/ | Four Factors weights |
| SRC-51 | 2025-2026 NBA Advanced Team Stats | https://www.nbastuffer.com/2025-2026-nba-team-stats/ | Team advanced stats |
| SRC-52 | Box Plus/Minus (BPM) | https://basketballstat.home.blog/2019/08/27/box-plus-minus-bpm/ | BPM formula |
| SRC-54 | DBPM and how it's calculated | https://www.reddit.com/r/nba/comments/1hkymkq/dbpm_and_how_it_s_calculated | DBPM limitations |
| SRC-55 | Basketball Advanced Analytics Betting | https://basketballbetstrategy.com/articles/basketball-advanced-analytics-betting/ | Net Rating |
| SRC-67 | Four year study of predictive accuracy | https://www.reddit.com/r/nba/comments/75j489/oc_four_year_study_of_the_predictive_accuracy_of/ | Metric correlations |
| SRC-71 | MSc IN STATISTICS | https://www.dept.aueb.gr/sites/default/files/stat/diplomatikes/pdf/Damoulaki.pdf | EPM Bayesian priors |
| SRC-76 | Guide to NBA Advanced Metrics | https://medium.com/hot-shot-nba/guide-to-nba-advanced-metrics-621b4030c2fa | AST%, REB% |
| SRC-77 | Basketball Analytics for Betting | https://betmana.co.uk/guide/basketball-analytics-for-betting/ | Four Factors, Net Rating |
| SRC-80 | Is Lebron Still A Dominating... | https://fivethirtyeight.com/features/winners-and-losers-in-our-updated-nba-season-predictions/ | RAPTOR tracking |
| SRC-88 | Lasso Multinomial Performance Indicators | https://arxiv.org/html/2406.09895v2 | APM |
| SRC-89 | Lineup Regularized Adjusted Plus-Minus | https://arxiv.org/html/2601.15000v1 | RAPM vs APM |
| SRC-90 | Player Impact Plus-Minus | https://www.bball-index.com/player-impact-plus-minus/ | PIPM |
| SRC-91 | Why Plus-Minus Needs a Thousand Games | https://nbaanalytic.com/articles/plus-minus-rapm-noise.html | APM methodology |
| SRC-92 | APBRmetrics | https://apbr.org/metrics/viewtopic.php?t=9995 | APM instability |
| SRC-97 | We're Predicting The Career Of Every NBA Player | https://fivethirtyeight.com/features/how-were-predicting-nba-player-career/ | CARMELO |
| SRC-104 | What's New In Our NBA Projections For 2016-17 | https://fivethirtyeight.com/features/whats-new-in-our-nba-projections-for-2016-17/ | CARMELO historical comparables |
| SRC-111 | Algorithmic NBA Player Acquisition | https://wsb.wharton.upenn.edu/wp-content/uploads/2023/12/Brill_2023_Q.pdf | DARKO academic validation |
| SRC-112 | About the Data - Basketball Index | https://www.bball-index.com/about/about-the-data/ | PIPM methodology |
| SRC-113 | Nylon Calculus: Introducing PIPM | https://fansided.com/2018/01/11/nylon-calculus-introducing-player-impact-plus-minus/ | PIPM R² = 0.875 |
| SRC-124 | Now that RAPTOR and RAPM are gone | https://www.reddit.com/r/nba/comments/16zza0y/now_that_raptor_and_rapm_are_gone_what_are_the/ | DARKO time decay |
| SRC-132 | The Top 50 NBA Draft Prospects | https://fivethirtyeight.com/features/the-top-50-nba-draft-prospects-according-to-our-carmelo-projections/ | CARMELO draft projections |
| SRC-174 | Introducing DARKO | https://www.nytimes.com/athletic/2613015/2021/05/26/introducing-darko-an-nba-playoffs-game-projection-and-betting-guide/ | DARKO projections |
| SRC-193 | hoopR Package Index | https://hoopr.sportsdataverse.org/reference/index.html | hoopR functions list |
| SRC-194 | Getting Started with hoopR | https://hoopr.sportsdataverse.org/articles/getting-started-hoopR.html | hoopR data sources |
| SRC-197 | NBA Data API | https://www.sportapidata.com/nba-data-api | SportAPI tracking data |
| SRC-198 | Every Free Public Basketball Data Source | https://nbaanalytic.com/articles/free-basketball-data-sources-ranked.html | Free data sources ranked |
| SRC-203 | swar/nba_api | https://github.com/swar/nba_api | nba_api GitHub |
| SRC-204 | basketball_reference_scraper | https://github.com/vishaalagartha/basketball_reference_scraper | Basketball-Reference scraper |
| SRC-207 | Chapter 2: Data Sources and Collection | https://datafield.dev/professional-basketball-analytics/part-01/chapter-02/ | Data sources comparison |
| SRC-214 | A Bayesian two-stage framework | https://pmc.ncbi.nlm.nih.gov/articles/PMC12671482/ | Play-by-play lineup extraction |
| SRC-215 | Play-by-play data analysis | http://www2.stat-athens.aueb.gr/~jbn/conferences/MathSport_presentations/TRACK%20B/B9%20-%20Game%20Strategy%20&%20Decision%20Making/Grasseti_Play-by-play%20data%20Analysis.pdf | Play-by-play fields |
| SRC-217 | Explaining Synergy's New Player Impact Stats | https://sportradar.com/content-hub/blog/explaining-synergys-new-player-impact-stats/ | Lineup data for plus-minus |
| SRC-218 | Dunks & Threes | https://dunksandthrees.com/ | EPM homepage |
| SRC-219 | DARKO DPM | https://www.darko.app/ | DARKO DPM leaderboard |
| SRC-220 | NBA Player Value Models | https://medium.com/@johnchenmbb/calculating-rapm-steps-1-and-2-of-my-summer-plan-1a78e1476b1f | RAPM calculation steps |