# NBA Player Impact ML Model: Data Sources Guide

## Executive Summary

This document provides a comprehensive guide to data sources for the NBA player impact ML model project, including where to obtain data, access methods (free vs. paid), and access requirements.

**Key Recommendations:**

- **Primary data source:** `nba_api` Python package for official NBA stats (free, comprehensive) [SRC-199][SRC-203][SRC-208]
- **Supplementary sources:** SportsDataverse (hoopR), Basketball-Reference, pbpstats for specific use cases [SRC-184][SRC-188][SRC-198]
- **Tracking data:** NBA API (aggregated metrics, free) or Second Spectrum via SportAPI Data (enterprise tier) [SRC-197][SRC-207]

---

## Part 1: Primary Data Sources (Recommended)

### 1.1 NBA API (stats.nba.com) via `nba_api` Python Package

**Access Method:**
- **Package:** `nba_api` (Python) [SRC-199][SRC-203][SRC-208]
- **Installation:** `pip install nba_api` [SRC-208]
- **Cost:** Free, no API key required [SRC-208][SRC-210]
- **Rate Limits:** ~1 request/second recommended; HTTP 429 errors if exceeded [SRC-207][SRC-211]

**Data Coverage:**
- **Historical:** 1946-present (box scores), 1996-present (play-by-play), 2013-present (tracking data) [SRC-197][SRC-207]
- **Endpoints:** 200+ endpoints covering player stats, team stats, box scores, play-by-play, shot charts, tracking data [SRC-206][SRC-208]

**Key Endpoints for This Project:**

| Endpoint Category | Specific Endpoints | Data Provided | Used For |
|------------------|-------------------|---------------|----------|
| **Player Stats** | `playercareerstats`, `playerdashboardbygeneralsplits` | Career totals, per-game stats, advanced stats (PER, TS%, USG%) | Tier 1-3 features (BPM, WS, PER inputs) [SRC-199][SRC-203] |
| **Team Stats** | `teamdashboardbygeneralsplits`, `teamyearbyyearstats` | Team offensive/defensive ratings, Four Factors, pace | Team-level features, Net Rating [SRC-207] |
| **Box Scores** | `boxscoreplayerstats`, `boxscoresummary` | Game-level player stats, lineup data | Play-by-play aggregation, stint extraction [SRC-207] |
| **Play-by-Play** | `playbyplayv2`, `playbyplayv3` | Event-level data (shots, assists, substitutions) | RAPM stint calculation, lineup data [SRC-214][SRC-220] |
| **Tracking Data** | `dashv2`, `playerdashptshotlog` | Contested shots, defensive positioning, speed/distance | Tracking features (EPM/RAPTOR-style) [SRC-197][SRC-207] |
| **Shot Charts** | `shotchartdetail` | Shot locations, shot types, defender distance | Spatial features, shot quality estimation [SRC-207] |

**Example Usage:**
```python
from nba_api.stats.endpoints import playercareerstats

# Get Nikola Jokić career stats
career = playercareerstats.PlayerCareerStats(player_id='203999')
df = career.season_totals_regular_season.get_data_frame()
```
[SRC-203][SRC-208]

**Pros:**
- Official league data, comprehensive coverage
- Free, no API key required
- Well-documented Python wrapper [SRC-203][SRC-206]
- Includes tracking data (aggregated metrics) [SRC-197][SRC-207]

**Cons:**
- Rate-limited (~1 req/sec); requires proper headers (User-Agent) [SRC-207][SRC-211]
- Undocumented API (community reverse-engineered) [SRC-211]
- Endpoints may change without notice [SRC-211]

---

### 1.2 SportsDataverse (hoopR for R, sportsdataverse-py for Python)

**Access Method:**
- **R Package:** `hoopR` [SRC-188][SRC-192][SRC-194]
- **Python Package:** `sportsdataverse-py` [SRC-184][SRC-195]
- **Cost:** Free, open-source [SRC-188][SRC-190]
- **Installation (R):** `install.packages('hoopR', repos = c('https://sportsdataverse.r-universe.dev', 'https://cloud.r-project.org'))` [SRC-192]
- **Installation (Python):** `pip install sportsdataverse` [SRC-184]

**Data Coverage:**
- **NBA:** 2002-present (play-by-play, box scores) [SRC-187][SRC-188]
- **Data Sources:** NBA Stats API, ESPN, KenPom (college), Basketball-Reference [SRC-188][SRC-194]

**Key Functions for This Project:**

| Function | Data Provided | Used For |
|----------|---------------|----------|
| `load_nba_pbp()` | Play-by-play data (tidy format) | RAPM stint extraction [SRC-193][SRC-220] |
| `load_nba_player_box()` | Player box scores | Tier 1-3 features [SRC-193] |
| `load_nba_team_box()` | Team box scores | Team-level features [SRC-193] |
| `load_nba_player_stats()` | Season-level player stats | Historical features [SRC-193] |
| `load_nba_team_stats()` | Season-level team stats | Team-level features [SRC-193] |
| `load_nba_rosters()` | Team rosters by season | Lineup data, teammate quality [SRC-193] |
| `load_nba_schedule()` | Game schedules | Temporal features, rest days [SRC-193] |

**Example Usage (R):**
```r
library(hoopR)

# Load NBA play-by-play data
pbp <- load_nba_pbp(seasons = 2024)

# Load player box scores
box <- load_nba_player_box(seasons = 2024)
```
[SRC-193][SRC-194]

**Pros:**
- Pre-cleaned, tidy data format [SRC-188][SRC-194]
- 600+ functions covering NBA Stats API, ESPN, KenPom [SRC-188]
- Bulk data loaders (`load_nba_*()`) for historical data [SRC-188][SRC-193]
- Active community maintenance [SRC-168][SRC-191]

**Cons:**
- R package more mature than Python version [SRC-184][SRC-195]
- Some endpoints require active KenPom subscription [SRC-190][SRC-194]

---

## Part 2: Supplementary Data Sources

### 2.1 Basketball-Reference (via scraping)

**Access Method:**
- **Python Package:** `basketball_reference_scraper` [SRC-204]
- **Cost:** Free (personal use), commercial use requires licensing [SRC-207][SRC-209]
- **Rate Limits:** 20 requests/minute; automated blocking if exceeded [SRC-204][SRC-212]

**Data Coverage:**
- **Historical:** 1946-present (box scores, advanced stats) [SRC-207][SRC-209]
- **Metrics:** Win Shares, BPM, VORP, PER (pre-computed) [SRC-198]

**Key Data for This Project:**

| Data Type | Specific Metrics | Used For |
|-----------|-----------------|----------|
| **Advanced Stats** | Win Shares, BPM, VORP, PER | Tier 2-4 features, target variable validation [SRC-198] |
| **Box Scores** | Game logs, season totals | Feature engineering [SRC-207] |
| **Shooting Splits** | eFG%, TS%, shot locations | Four Factors, shooting efficiency [SRC-207] |

**Example Usage:**
```python
from basketball_reference_scraper import players

# Get player season stats
stats = players.get_stats('LeBron James', season=2024)
```
[SRC-204]

**Pros:**
- Pre-computed advanced metrics (Win Shares, BPM, VORP) [SRC-198]
- Comprehensive historical data (1946-present) [SRC-207][SRC-209]
- No API key required [SRC-198]

**Cons:**
- Requires scraping (not official API) [SRC-207]
- Rate-limited (20 req/min); terms of service restrict commercial use [SRC-204][SRC-207][SRC-212]
- Risk of IP blocking if rate limits exceeded [SRC-212]

---

### 2.2 pbpstats.com

**Access Method:**
- **Website:** https://www.pbpstats.com/ [SRC-198]
- **Cost:** Free [SRC-198]
- **Access:** Web scraping or manual download [SRC-198]

**Data Coverage:**
- **NBA:** 2000-present (play-by-play, lineup data) [SRC-198]
- **Metrics:** Lineup net ratings, possession-level data [SRC-198]

**Key Data for This Project:**

| Data Type | Specific Metrics | Used For |
|-----------|-----------------|----------|
| **Lineup Data** | 5-player combination net ratings | RAPM stint extraction, lineup optimization [SRC-198][SRC-217] |
| **Play-by-Play** | Possession-level events | RAPM calculation, stint identification [SRC-220] |

**Pros:**
- Specialized in lineup and possession-level data [SRC-198]
- Free access [SRC-198]

**Cons:**
- Narrow scope (only lineups and play-by-play) [SRC-198]
- Requires scraping (no official API) [SRC-198]

---

### 2.3 SportAPI Data (Enterprise Tracking Data)

**Access Method:**
- **API:** https://www.sportapidata.com/nba-data-api [SRC-197]
- **Cost:** Free tier (1,000 req/day), Enterprise tier for tracking data [SRC-196][SRC-197]
- **Data Source:** Second Spectrum (official NBA tracking provider) [SRC-197]

**Data Coverage:**
- **Historical:** 1946-present (box scores), 1996-present (play-by-play), 2013-present (tracking) [SRC-197]
- **Tracking Metrics:** Player position, speed, touches, contested shots [SRC-197]

**Key Data for This Project:**

| Data Type | Specific Metrics | Used For |
|-----------|-----------------|----------|
| **Tracking Data** | Player position, speed, distance, touches | EPM/RAPTOR-style tracking features [SRC-197] |
| **Contested Shots** | Shot defender distance, contest rate | Defensive impact features [SRC-197] |
| **Shot Locations** | X/Y coordinates, shot type | Spatial features, shot quality [SRC-197] |

**Pricing:**
- **Free Tier:** 100 req/min, 1,000 req/day (scores, box scores, play-by-play) [SRC-196]
- **Enterprise Tier:** Tracking data (position, speed, touches) — contact for pricing [SRC-197]

**Pros:**
- Official Second Spectrum tracking data [SRC-197]
- Comprehensive historical coverage (1946-present) [SRC-197]
- Free tier available for non-tracking data [SRC-196]

**Cons:**
- Tracking data requires enterprise tier (paid) [SRC-197]
- Usage restrictions for betting/broadcast applications [SRC-197]

---

## Part 3: Additional Free Sources Summary

| Source | Best For | Cost | Watch Out For | Source |
|--------|----------|------|---------------|--------|
| **nba_api** | Everything current; official stats | Free | stats.nba.com rate limits (~1 req/sec) | [SRC-198][SRC-208] |
| **Basketball-Reference** | History, Win Shares, BPM, VORP | Free | Scraping terms, 20 req/min rate limit | [SRC-198][SRC-204] |
| **pbpstats** | Lineups & play-by-play possessions | Free | Narrow scope | [SRC-198] |
| **SportsDataverse (hoopR)** | Clean play-by-play, bulk loaders | Free | R package more mature than Python | [SRC-188][SRC-198] |
| **Big Balls Sports Data** | Real-time scores, box scores, props | Free (1,000 req/day) | Limited to 1,000 req/day (2,000 with GitHub) | [SRC-196] |

[SRC-198]

---

## References

| ID | Title | URL | Key Claims Supported |
|----|-------|-----|---------------------|
| SRC-168 | About - SportsDataverse | https://www.sportsdataverse.org/about | SportsDataverse packages |
| SRC-184 | sportsdataverse - PyPI | https://pypi.org/project/sportsdataverse/ | sportsdataverse-py |
| SRC-187 | hoopR-nba-data | https://github.com/sportsdataverse/hoopR-nba-data | hoopR NBA data 2002-present |
| SRC-188 | hoopR Documentation | https://hoopr.sportsdataverse.org/ | hoopR functions |
| SRC-190 | SportsDataverse Packages | https://www.sportsdataverse.org/packages | hoopR description |
| SRC-191 | Blog - SportsDataverse | https://www.sportsdataverse.org/blog | SportsDataverse history |
| SRC-192 | hoopR: Access Men's Basketball Play by Play Data | https://sportsdataverse.r-universe.dev/hoopR | hoopR installation |
| SRC-193 | hoopR Package Index | https://hoopr.sportsdataverse.org/reference/index.html | hoopR functions list |
| SRC-194 | Getting Started with hoopR | https://hoopr.sportsdataverse.org/articles/getting-started-hoopR.html | hoopR data sources |
| SRC-195 | sdv-py | https://sportsdataverse-py.sportsdataverse.org/ | sportsdataverse-py |
| SRC-196 | NBA API \| Big Balls Sports Data | https://bigballsdata.com/nba-api | Big Balls free tier |
| SRC-197 | NBA Data API | https://www.sportapidata.com/nba-data-api | SportAPI tracking data |
| SRC-198 | Every Free Public Basketball Data Source | https://nbaanalytic.com/articles/free-basketball-data-sources-ranked.html | Free data sources ranked |
| SRC-199 | nba_api | https://pypi.org/project/nba_api/ | nba_api package |
| SRC-203 | swar/nba_api | https://github.com/swar/nba_api | nba_api GitHub |
| SRC-204 | basketball_reference_scraper | https://github.com/vishaalagartha/basketball_reference_scraper | Basketball-Reference scraper |
| SRC-206 | swar/nba_api \| DeepWiki | https://deepwiki.com/swar/nba_api | nba_api documentation |
| SRC-207 | Chapter 2: Data Sources and Collection | https://datafield.dev/professional-basketball-analytics/part-01/chapter-02/ | Data sources comparison |
| SRC-208 | Getting Started with nba_api | https://nbaanalytic.com/articles/nba-api-getting-started.html | nba_api tutorial |
| SRC-209 | Basketball-Reference API | https://www.apisports.net/providers/basketball-reference | Basketball-Reference pricing |
| SRC-210 | NBA API - Free Public APIs | https://openpublicapis.com/api/nba-api | nba_api documentation |
| SRC-211 | NBA Stats API | https://www.xscanhub.com/apis/nba-com | NBA Stats API details |
| SRC-212 | Does anyone here have experience bypassing | https://www.reddit.com/r/sportsanalytics/comments/11doqfg/does_anyone_here_have_experience_bypassing_the/ | Basketball-Reference rate limits |
| SRC-214 | A Bayesian two-stage framework | https://pmc.ncbi.nlm.nih.gov/articles/PMC12671482/ | Play-by-play lineup extraction |
| SRC-215 | Play-by-play data analysis | http://www2.stat-athens.aueb.gr/~jbn/conferences/MathSport_presentations/TRACK%20B/B9%20-%20Game%20Strategy%20&%20Decision%20Making/Grasseti_Play-by-play%20data%20Analysis.pdf | Play-by-play fields |
| SRC-217 | Explaining Synergy's New Player Impact Stats | https://sportradar.com/content-hub/blog/explaining-synergys-new-player-impact-stats/ | Lineup data for plus-minus |
| SRC-220 | NBA Player Value Models | https://medium.com/@johnchenmbb/calculating-rapm-steps-1-and-2-of-my-summer-plan-1a78e1476b1f | RAPM calculation steps |