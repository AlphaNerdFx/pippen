# NBA Player Impact ML Model: Data Pipeline & Compliance Guide

## Executive Summary

This document provides a recommended data acquisition pipeline and compliance checklist for the NBA player impact ML model project, including rate limiting, terms of service, and data quality validation.

---

## Part 1: Recommended Data Acquisition Pipeline

### 1.1 Phase 1: Initial Data Collection (Weeks 1-2)

**Priority Data:**
1. **Box scores (2015-2023):** Use `nba_api` or SportsDataverse `load_nba_player_box()` [SRC-193][SRC-203]
2. **Play-by-play (2015-2023):** Use SportsDataverse `load_nba_pbp()` (tidy format) [SRC-193][SRC-194]
3. **Team stats (2015-2023):** Use `nba_api` `teamyearbyyearstats` [SRC-203]

**Storage:**
- Store as Parquet files on S3/GCS or PostgreSQL database [SRC-146]
- Organize by season: `data/nba/box_scores/2015.parquet`, `data/nba/pbp/2015.parquet`

**Example Pipeline:**
```python
from nba_api.stats.endpoints import teamyearbyyearstats
import pandas as pd

# Loop through seasons
for season in range(2015, 2024):
    teams = teamyearbyyearstats.TeamYearByYearStats(season=season)
    df = teams.team_stats.get_data_frame()
    df.to_parquet(f'data/nba/team_stats/{season}.parquet')
```
[SRC-203]

---

### 1.2 Phase 2: Advanced Metrics Calculation (Weeks 3-4)

**Priority Calculations:**
1. **RAPM:** Extract lineup stints from play-by-play, apply ridge regression [SRC-220]
2. **Four Factors:** Calculate from box scores (eFG%, TOV%, OREB%, FTR) [SRC-46][SRC-49]
3. **Net Rating:** Calculate from team ORtg/DRtg [SRC-55][SRC-77]

**Tools:**
- Use `nba_api` for raw data, custom Python scripts for RAPM calculation [SRC-203][SRC-220]
- Use SportsDataverse `load_nba_pbp()` for pre-cleaned play-by-play [SRC-193]

**Example RAPM Calculation:**
```python
import pandas as pd
from sklearn.linear_model import Ridge

# Load play-by-play data
pbp = pd.read_parquet('data/nba/pbp/2023.parquet')

# Extract lineup stints (5-player combinations)
stints = extract_lineup_stints(pbp)

# Calculate scoring margin per 100 possessions
stints['margin_per_100'] = stints['margin'] / stints['possessions'] * 100

# Apply ridge regression
X = create_design_matrix(stints)  # Player presence (+1/-1/0)
y = stints['margin_per_100']
rapm_model = Ridge(alpha=1000)  # Ridge penalty
rapm_model.fit(X, y)
player_rapm = rapm_model.coef_
```
[SRC-34][SRC-220]

---

### 1.3 Phase 3: Target Variable Integration (Weeks 5-6)

**Priority Targets:**
1. **EPM:** If API available, download from Dunks & Threes [SRC-36][SRC-218]
2. **DARKO/DPM:** If API available, download from DARKO.app [SRC-174][SRC-219]
3. **Win Shares, BPM:** Scrape from Basketball-Reference (respect rate limits) [SRC-198][SRC-204]

**Storage:**
- Store as separate tables: `targets/epm.parquet`, `targets/darko.parquet`, `targets/win_shares.parquet`

**Example Basketball-Reference Scraping:**
```python
from basketball_reference_scraper import players
import time

# Get Win Shares for all players
players_list = get_all_players()  # Custom function
ws_data = []

for player in players_list:
    try:
        stats = players.get_stats(player, season=2023)
        ws_data.append(stats)
        time.sleep(3)  # Respect 20 req/min rate limit
    except Exception as e:
        print(f"Error scraping {player}: {e}")
        time.sleep(60)  # Wait if rate limited

ws_df = pd.DataFrame(ws_data)
ws_df.to_parquet('targets/win_shares.parquet')
```
[SRC-204][SRC-212]

---

### 1.4 Phase 4: Tracking Data Integration (Weeks 7-8, Optional)

**Priority Tracking Metrics:**
1. **Contested shots:** From NBA API `playerdashptshotlog` [SRC-207]
2. **Defensive positioning:** From NBA API `dashv2` (if available) [SRC-207]
3. **Speed/distance:** From SportAPI Data enterprise tier (if budget allows) [SRC-197]

**Use Cases:**
- EPM-style tracking features [SRC-36]
- Defensive impact estimation [SRC-47][SRC-54]

**Example Tracking Data Extraction:**
```python
from nba_api.stats.endpoints import playerdashptshotlog

# Get contested shot data for 2023 season
contested = playerdashptshotlog.PlayerDashPtShotLog(
    season='2023',
    season_type='Regular Season'
)
contested_df = contested.shot_log.get_data_frame()

# Calculate contest rate
contested_df['contest_rate'] = contested_df['CLOSE_DEF_DIST'] < 4  # Within 4 feet
contested_df.to_parquet('data/nba/tracking/contested_shots_2023.parquet')
```
[SRC-207]

---

## Part 2: Rate Limiting Compliance

### 2.1 Rate Limits by Source

| Source | Rate Limit | Compliance Strategy |
|--------|-----------|---------------------|
| **NBA API (nba_api)** | ~1 req/sec [SRC-207][SRC-211] | Add `time.sleep(1)` between requests; use proper headers (User-Agent) [SRC-211] |
| **Basketball-Reference** | 20 req/min [SRC-204][SRC-212] | Use `basketball_reference_scraper` package (abstracts waiting logic) [SRC-204] |
| **SportsDataverse** | No explicit limit (uses NBA API internally) | Follow NBA API rate limits [SRC-188][SRC-207] |
| **pbpstats** | No explicit limit | Scrape responsibly (1 req/3-5 sec) [SRC-207] |

**Example Rate Limiting Implementation:**
```python
import time
from nba_api.stats.endpoints import playercareerstats

def safe_api_call(endpoint_func, **kwargs):
    """Make API call with rate limiting."""
    headers = {'User-Agent': 'NBA-Player-Impact-Model/1.0'}
    try:
        result = endpoint_func(**kwargs)
        time.sleep(1)  # Respect 1 req/sec limit
        return result
    except Exception as e:
        print(f"API error: {e}")
        time.sleep(60)  # Wait if rate limited
        return None

# Usage
for player_id in player_ids:
    career = safe_api_call(playercareerstats.PlayerCareerStats, player_id=player_id)
```
[SRC-211][SRC-212]

---

## Part 3: Terms of Service Compliance

### 3.1 Commercial Use & Redistribution

| Source | Commercial Use | Redistribution | Notes |
|--------|---------------|----------------|-------|
| **NBA API** | Restricted (check terms) | Restricted | Free for personal/research use; commercial requires licensing [SRC-207][SRC-211] |
| **Basketball-Reference** | Requires licensing [SRC-207][SRC-209] | Restricted | Free for personal use; commercial use requires Stathead subscription or licensing [SRC-209] |
| **SportsDataverse** | Open-source (check underlying sources) | Allowed (open-source) | Underlying NBA API terms still apply [SRC-188][SRC-190] |
| **pbpstats** | Unclear (contact for commercial) | Unclear | Free for personal use; contact for commercial licensing [SRC-198] |

**Compliance Checklist:**

- [ ] Verify intended use (personal/research vs. commercial) [SRC-207][SRC-209]
- [ ] Review NBA API terms of service (stats.nba.com) [SRC-211]
- [ ] Review Basketball-Reference terms (sports-reference.com) [SRC-209]
- [ ] If commercial use planned, contact sources for licensing [SRC-197][SRC-209]
- [ ] Do not redistribute raw data (only derived metrics/models) [SRC-207][SRC-209]

---

## Part 4: Data Quality Validation

### 4.1 Completeness Checks

**Verify All Games Present:**
```python
from hoopR import load_nba_schedule, load_nba_pbp

# Load schedule
schedule = load_nba_schedule(seasons=2023)
total_games = len(schedule)

# Load play-by-play
pbp = load_nba_pbp(seasons=2023)
games_with_pbp = pbp['game_id'].nunique()

# Check completeness
if games_with_pbp < total_games:
    missing_games = set(schedule['game_id']) - set(pbp['game_id'].unique())
    print(f"Missing {len(missing_games)} games: {missing_games}")
```
[SRC-193][SRC-194]

**Check for Missing Player IDs:**
```python
from nba_api.stats.endpoints import boxscoreplayerstats

# Load box scores
box = boxscoreplayerstats.BoxScorePlayerStats(game_id='0022300001')
box_df = box.player_stats.get_data_frame()

# Check for missing player IDs
if box_df['PERSON_ID'].isnull().any():
    print(f"Found {box_df['PERSON_ID'].isnull().sum()} missing player IDs")
```
[SRC-203]

---

### 4.2 Consistency Checks

**Verify Box Score Totals Match Play-by-Play:**
```python
import pandas as pd

# Load box scores and play-by-play
box = pd.read_parquet('data/nba/box_scores/2023.parquet')
pbp = pd.read_parquet('data/nba/pbp/2023.parquet')

# Aggregate play-by-play to box score level
pbp_agg = pbp.groupby(['game_id', 'player_id']).agg({
    'points': 'sum',
    'rebounds': 'sum',
    'assists': 'sum'
}).reset_index()

# Compare to box scores
merged = pd.merge(box, pbp_agg, on=['game_id', 'player_id'], suffixes=('_box', '_pbp'))
discrepancies = merged[merged['PTS_box'] != merged['points_pbp']]

if len(discrepancies) > 0:
    print(f"Found {len(discrepancies)} discrepancies between box scores and play-by-play")
```
[SRC-214][SRC-215]

**Check for Duplicate Entries:**
```python
import pandas as pd

# Load data
box = pd.read_parquet('data/nba/box_scores/2023.parquet')

# Check for duplicates
duplicates = box[box.duplicated(subset=['game_id', 'player_id'], keep=False)]

if len(duplicates) > 0:
    print(f"Found {len(duplicates)} duplicate entries")
    print(duplicates[['game_id', 'player_id', 'team_abbreviation']])
```
[SRC-193]

---

### 4.3 Accuracy Checks

**Compare Calculated RAPM to Published Values:**
```python
import pandas as pd
from sklearn.metrics import mean_squared_error

# Load calculated RAPM
rapm_calculated = pd.read_parquet('targets/rapm_calculated.parquet')

# Load published RAPM (if available, e.g., from Dunks & Threes)
rapm_published = pd.read_parquet('targets/rapm_published.parquet')

# Merge and compare
merged = pd.merge(rapm_calculated, rapm_published, on='player_id', suffixes=('_calc', '_pub'))
rmse = mean_squared_error(merged['RAPM_calc'], merged['RAPM_pub'], squared=False)

print(f"RAPM RMSE vs. published: {rmse:.2f}")
print(f"Correlation: {merged['RAPM_calc'].corr(merged['RAPM_pub']):.3f}")
```
[SRC-220][SRC-221]

**Validate Four Factors Against NBA.com:**
```python
from nba_api.stats.endpoints import teamdashboardbygeneralsplits

# Load calculated Four Factors
ff_calculated = pd.read_parquet('targets/four_factors.parquet')

# Get NBA.com advanced stats
nba_adv = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
    season='2023',
    season_type='Regular Season'
)
nba_adv_df = nba_adv.team_dashboard.get_data_frame()

# Compare eFG%
merged = pd.merge(ff_calculated, nba_adv_df, on='team_id', suffixes=('_calc', '_nba'))
efg_rmse = mean_squared_error(merged['eFG%_calc'], merged['eFG_PCT_nba'], squared=False)

print(f"eFG% RMSE vs. NBA.com: {efg_rmse:.3f}")
```
[SRC-46][SRC-51]

---

### 4.4 Temporal Integrity Checks

**Ensure No Future Data Leakage:**
```python
import pandas as pd

# Load data with timestamps
data = pd.read_parquet('data/nba/box_scores/2023.parquet')

# Check for future dates
max_date = data['game_date'].max()
train_cutoff = '2023-06-01'  # Example: end of regular season

future_data = data[data['game_date'] > train_cutoff]

if len(future_data) > 0:
    print(f"WARNING: Found {len(future_data)} records with future dates (after {train_cutoff})")
    print("Remove these from training set to prevent data leakage")
```
[SRC-146]

**Verify Play-by-Play Timestamps Sequential:**
```python
import pandas as pd

# Load play-by-play
pbp = pd.read_parquet('data/nba/pbp/2023.parquet')

# Check for sequential timestamps within games
pbp_sorted = pbp.sort_values(['game_id', 'period', 'time_remaining'])
pbp_sorted['time_diff'] = pbp_sorted.groupby('game_id')['time_remaining'].diff()

# Check for negative time differences (out of order)
out_of_order = pbp_sorted[pbp_sorted['time_diff'] < 0]

if len(out_of_order) > 0:
    print(f"Found {len(out_of_order)} events out of temporal order")
    print(out_of_order[['game_id', 'period', 'time_remaining']].head())
```
[SRC-215]

---

## References

| ID | Title | URL | Key Claims Supported |
|----|-------|-----|---------------------|
| SRC-34 | Lineup Regularized Adjusted Plus-Minus | https://arxiv.org/abs/2601.15000 | RAPM methodology |
| SRC-36 | About Estimated Plus-Minus | https://dunksandthrees.com/about/epm | EPM methodology |
| SRC-46 | Dean Oliver's Four Factors Revisited | https://arxiv.org/abs/2305.13032 | Four Factors |
| SRC-47 | About Box Plus/Minus | https://www.basketball-reference.com/about/bpm2.html | BPM methodology |
| SRC-49 | NBA Advanced Stats: Four Factors | https://hoopshabit.com/2014/07/23/nba-advanced-stats-four-factors-winning/ | Four Factors weights |
| SRC-51 | 2025-2026 NBA Advanced Team Stats | https://www.nbastuffer.com/2025-2026-nba-team-stats/ | Team advanced stats |
| SRC-54 | DBPM and how it's calculated | https://www.reddit.com/r/nba/comments/1hkymkq/dbpm_and_how_it_s_calculated | DBPM limitations |
| SRC-55 | Basketball Advanced Analytics Betting | https://basketballbetstrategy.com/articles/basketball-advanced-analytics-betting/ | Net Rating |
| SRC-77 | Basketball Analytics for Betting | https://betmana.co.uk/guide/basketball-analytics-for-betting/ | Four Factors, Net Rating |
| SRC-146 | Practitioners guide to MLOps | https://services.google.com/fh/files/misc/practitioners_guide_to_mlops_whitepaper.pdf | MLOps data storage, temporal splits |
| SRC-174 | Introducing DARKO | https://www.nytimes.com/athletic/2613015/2021/05/26/introducing-darko-an-nba-playoffs-game-projection-and-betting-guide/ | DARKO projections |
| SRC-188 | hoopR Documentation | https://hoopr.sportsdataverse.org/ | hoopR functions |
| SRC-190 | SportsDataverse Packages | https://www.sportsdataverse.org/packages | hoopR description |
| SRC-193 | hoopR Package Index | https://hoopr.sportsdataverse.org/reference/index.html | hoopR functions list |
| SRC-194 | Getting Started with hoopR | https://hoopr.sportsdataverse.org/articles/getting-started-hoopR.html | hoopR data sources |
| SRC-197 | NBA Data API | https://www.sportapidata.com/nba-data-api | SportAPI tracking data |
| SRC-198 | Every Free Public Basketball Data Source | https://nbaanalytic.com/articles/free-basketball-data-sources-ranked.html | Free data sources ranked |
| SRC-203 | swar/nba_api | https://github.com/swar/nba_api | nba_api GitHub |
| SRC-204 | basketball_reference_scraper | https://github.com/vishaalagartha/basketball_reference_scraper | Basketball-Reference scraper |
| SRC-207 | Chapter 2: Data Sources and Collection | https://datafield.dev/professional-basketball-analytics/part-01/chapter-02/ | Data sources comparison, rate limits |
| SRC-209 | Basketball-Reference API | https://www.apisports.net/providers/basketball-reference | Basketball-Reference pricing |
| SRC-211 | NBA Stats API | https://www.xscanhub.com/apis/nba-com | NBA Stats API details |
| SRC-212 | Does anyone here have experience bypassing | https://www.reddit.com/r/sportsanalytics/comments/11doqfg/does_anyone_here_have_experience_bypassing_the/ | Basketball-Reference rate limits |
| SRC-214 | A Bayesian two-stage framework | https://pmc.ncbi.nlm.nih.gov/articles/PMC12671482/ | Play-by-play lineup extraction |
| SRC-215 | Play-by-play data analysis | http://www2.stat-athens.aueb.gr/~jbn/conferences/MathSport_presentations/TRACK%20B/B9%20-%20Game%20Strategy%20&%20Decision%20Making/Grasseti_Play-by-play%20data%20Analysis.pdf | Play-by-play fields |
| SRC-218 | Dunks & Threes | https://dunksandthrees.com/ | EPM homepage |
| SRC-219 | DARKO DPM | https://www.darko.app/ | DARKO DPM leaderboard |
| SRC-220 | NBA Player Value Models | https://medium.com/@johnchenmbb/calculating-rapm-steps-1-and-2-of-my-summer-plan-1a78e1476b1f | RAPM calculation steps |
| SRC-221 | The Historical RAPM Project | https://squared2020.com/2026/04/29/the-historical-rapm-project/ | Historical RAPM reconstruction |