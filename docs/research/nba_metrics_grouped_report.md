# NBA Advanced Metrics: Grouped by Type and Aspect

This report organizes NBA advanced metrics by type (individual vs. team) and the aspect of the game they measure (offense, defense, all-in-one, projection, etc.).

---

## Individual Advanced Metrics

### Offensive Production & Efficiency

| Metric | Developer | Aspect Covered | Key Formula Elements | Reliability | Tier | Source IDs |
|--------|-----------|----------------|---------------------|-------------|------|------------|
| **PER** | John Hollinger [SRC-16][SRC-20] | Per-minute production, pace-adjusted | Box score events weighted by point value; pace normalization [SRC-16][SRC-26] | 50-60% | Tier 4 | SRC-16, SRC-20, SRC-23, SRC-26, SRC-28, SRC-29, SRC-30, SRC-67 |
| **BPM (OBPM)** | Daniel Myers [SRC-47] | Points above average per 100 poss (offense) | Position/role-aware box score regression on RAPM [SRC-47][SRC-52] | ~85% (offense only) | Tier 3 | SRC-47, SRC-50, SRC-52, SRC-54, SRC-67 |
| **EPM (O-EPM)** | Taylor Snarr [SRC-36] | Predicted offensive impact per 100 poss | Estimated Skills + RAPM with Bayesian prior [SRC-36][SRC-71] | 85-90% | Tier 1 | SRC-36, SRC-37, SRC-39, SRC-71 |
| **RAPM (O-RAPM)** | Joe Sill [SRC-34] | Offensive scoring margin per 100 poss | Ridge regression on lineup stints [SRC-34][SRC-44] | 80-85% | Tier 2 | SRC-33, SRC-34, SRC-38, SRC-40, SRC-41, SRC-43, SRC-44, SRC-45, SRC-61, SRC-67, SRC-68, SRC-73 |
| **True Shooting (TS%)** | Various | Scoring efficiency accounting for 2PT, 3PT, FT | PTS / (2 × (FGA + 0.44 × FTA)) [SRC-2][SRC-10] | 75-80% | Tier 3 | SRC-2, SRC-10 |
| **Usage Rate (USG%)** | Various | Percentage of team possessions used by player | (FGA + 0.44 × FTA + TOV) / team possessions [SRC-11][SRC-15] | 65-70% | Tier 3 | SRC-11, SRC-15, SRC-76 |
| **PIPM (O-PIPM)** | Nathan Walker [SRC-90][SRC-113] | Predicted offensive impact per 100 poss | Box prior + luck-adjusted on/off [SRC-113][SRC-127] | 80-85% | Tier 2 | SRC-90, SRC-112, SRC-113, SRC-126, SRC-127, SRC-129 |
| **DARKO (O-DARKO)** | BBall Index [SRC-111][SRC-133] | Predicted offensive impact per 100 poss (game-by-game) | Kalman filtering + exponential decay [SRC-111][SRC-124] | 85-90% | Tier 1 | SRC-109, SRC-111, SRC-124, SRC-133 |

### Defensive Impact

| Metric | Developer | Aspect Covered | Key Formula Elements | Reliability | Tier | Source IDs |
|--------|-----------|----------------|---------------------|-------------|------|------------|
| **BPM (DBPM)** | Daniel Myers [SRC-47] | Points above average per 100 poss (defense) | Total BPM - OBPM; box score limited [SRC-47][SRC-54] | 50-60% | Tier 4 | SRC-47, SRC-50, SRC-52, SRC-54 |
| **EPM (D-EPM)** | Taylor Snarr [SRC-36] | Predicted defensive impact per 100 poss | Estimated Skills + RAPM (defensive component) [SRC-36][SRC-71] | 80-85% | Tier 1 | SRC-36, SRC-37, SRC-39, SRC-71 |
| **RAPM (D-RAPM)** | Joe Sill [SRC-34] | Defensive scoring margin per 100 poss | Separate RAPM regression on points allowed [SRC-44] | 80-85% | Tier 2 | SRC-33, SRC-34, SRC-38, SRC-40, SRC-41, SRC-43, SRC-44, SRC-45, SRC-61, SRC-67, SRC-68, SRC-73 |
| **Defensive Rating (DRtg)** | Dean Oliver [SRC-46][SRC-55] | Points allowed per 100 possessions | (Opponent PTS / Opponent Possessions) × 100 [SRC-55][SRC-77] | 85-90% | Tier 2 | SRC-46, SRC-55, SRC-77 |
| **PIPM (D-PIPM)** | Nathan Walker [SRC-90][SRC-113] | Predicted defensive impact per 100 poss | Box prior + luck-adjusted on/off [SRC-113][SRC-127] | 80-85% | Tier 2 | SRC-90, SRC-112, SRC-113, SRC-126, SRC-127, SRC-129 |
| **DARKO (D-DARKO)** | BBall Index [SRC-111][SRC-133] | Predicted defensive impact per 100 poss (game-by-game) | Kalman filtering + exponential decay [SRC-111][SRC-124] | 85-90% | Tier 1 | SRC-109, SRC-111, SRC-124, SRC-133 |

### All-in-One Impact

| Metric | Developer | Aspect Covered | Key Formula Elements | Reliability | Tier | Source IDs |
|--------|-----------|----------------|---------------------|-------------|------|------------|
| **Win Shares** | Bill James [SRC-17][SRC-22] | Contribution to team wins | Offensive WS + Defensive WS [SRC-17][SRC-18] | 75-80% | Tier 2 | SRC-17, SRC-18, SRC-21, SRC-22, SRC-47, SRC-50, SRC-64, SRC-67 |
| **EPM (Total)** | Taylor Snarr [SRC-36] | Total impact per 100 possessions | O-EPM + D-EPM [SRC-36][SRC-71] | 85-90% | Tier 1 | SRC-36, SRC-37, SRC-39, SRC-71 |
| **RAPM (Total)** | Joe Sill [SRC-34] | Total scoring margin per 100 poss | O-RAPM + D-RAPM [SRC-34][SRC-44] | 80-85% | Tier 2 | SRC-33, SRC-34, SRC-38, SRC-40, SRC-41, SRC-43, SRC-44, SRC-45, SRC-61, SRC-67, SRC-68, SRC-73 |
| **BPM (Total)** | Daniel Myers [SRC-47] | Total points above average per 100 poss | OBPM + DBPM [SRC-47][SRC-52] | 70-75% | Tier 3 | SRC-47, SRC-50, SRC-52, SRC-54, SRC-64, SRC-67 |
| **PIE** | NBA Stats [SRC-1] | Percentage of game events achieved | (Positive events - negative events) / all events [SRC-1][SRC-6] | 70-75% | Tier 3 | SRC-1, SRC-6, SRC-85 |
| **RAPTOR** | FiveThirtyEight [SRC-80] | Total impact per 100 possessions | Box score + tracking + on/off [SRC-80][SRC-87] | 80-85% | Tier 2 | SRC-80, SRC-81, SRC-86, SRC-87 |
| **LEBRON** | BBall Index [SRC-78] | Total impact per 100 possessions | Box prior + luck-adjusted on/off [SRC-78][SRC-82] | 80-85% | Tier 2 | SRC-78, SRC-82, SRC-83, SRC-120 |
| **PIPM (Total)** | Nathan Walker [SRC-90][SRC-113] | Total impact per 100 possessions | O-PIPM + D-PIPM [SRC-113][SRC-127] | 80-85% | Tier 2 | SRC-90, SRC-112, SRC-113, SRC-126, SRC-127, SRC-129 |
| **DARKO (Total)** | BBall Index [SRC-111][SRC-133] | Total impact per 100 possessions (game-by-game) | O-DARKO + D-DARKO [SRC-111][SRC-133] | 85-90% | Tier 1 | SRC-109, SRC-111, SRC-124, SRC-133 |
| **RPM** | Engelmann/Illardi [SRC-37][SRC-42] | Total impact per 100 possessions | Box prior + RAPM [SRC-37][SRC-42] | 80-85% | Tier 2 | SRC-37, SRC-42, SRC-67, SRC-80 |

### Cumulative Impact (Volume-Based)

| Metric | Developer | Aspect Covered | Key Formula Elements | Reliability | Tier | Source IDs |
|--------|-----------|----------------|---------------------|-------------|------|------------|
| **TPA** | Derived from BPM [SRC-108] | Total points added over season | OPA + DPS = OBPM × poss + DBPM × poss [SRC-121][SRC-122] | 70-75% | Tier 3 | SRC-108, SRC-121, SRC-122 |
| **VORP** | Basketball Reference [SRC-67] | Value over replacement (cumulative) | BPM × minutes, adjusted for replacement level [SRC-67] | 70-75% | Tier 3 | SRC-67 |

### Projection Systems (Career Forecasting)

| Metric | Developer | Aspect Covered | Key Formula Elements | Reliability | Tier | Source IDs |
|--------|-----------|----------------|---------------------|-------------|------|------------|
| **CARMELO** | FiveThirtyEight [SRC-97][SRC-99] | Career arc projection (WARP) | RPM (2/3) + BPM (1/3) + historical comparables [SRC-99][SRC-105] | N/A | N/A | SRC-96, SRC-97, SRC-99, SRC-101, SRC-102, SRC-103, SRC-104, SRC-105, SRC-106, SRC-110, SRC-132, SRC-134, SRC-135, SRC-136, SRC-137, SRC-138 |

### Historical/Foundation Metrics

| Metric | Developer | Aspect Covered | Key Formula Elements | Reliability | Tier | Source IDs |
|--------|-----------|----------------|---------------------|-------------|------|------------|
| **APM** | Winston/Sagarin/Rosenbaum [SRC-88][SRC-95] | Scoring margin per 100 poss (OLS regression) | Lineup regression, no regularization [SRC-88][SRC-91] | 50-60% | Tier 4 | SRC-88, SRC-89, SRC-91, SRC-92, SRC-94, SRC-95, SRC-125 |

### Playmaking & Ball Handling

| Metric | Developer | Aspect Covered | Key Formula Elements | Reliability | Tier | Source IDs |
|--------|-----------|----------------|---------------------|-------------|------|------------|
| **Assist Percentage (AST%)** | Various | Percentage of teammate baskets assisted | AST / teammate FGM while on court [SRC-15][SRC-76] | 70-75% | Tier 3 | SRC-15, SRC-76 |
| **Assist-to-Turnover Ratio** | Various | Ball security and playmaking efficiency | AST / TOV [SRC-4][SRC-12] | 65-70% | Tier 3 | SRC-4, SRC-12 |

### Rebounding

| Metric | Developer | Aspect Covered | Key Formula Elements | Reliability | Tier | Source IDs |
|--------|-----------|----------------|---------------------|-------------|------|------------|
| **Rebound Percentage (REB%, ORB%, DRB%)** | Various | Percentage of available rebounds grabbed | REB / (REB + Opp REB) [SRC-15][SRC-76] | 75-80% | Tier 3 | SRC-15, SRC-76 |

---

## Team Advanced Metrics

### Overall Team Efficiency

| Metric | Developer | Aspect Covered | Key Formula Elements | Reliability | Tier | Source IDs |
|--------|-----------|----------------|---------------------|-------------|------|------------|
| **Offensive Rating (ORtg)** | Dean Oliver [SRC-46][SRC-55] | Points scored per 100 possessions | (Team PTS / Team Possessions) × 100 [SRC-55][SRC-77] | 85-90% | Tier 2 | SRC-46, SRC-48, SRC-51, SRC-55, SRC-77 |
| **Defensive Rating (DRtg)** | Dean Oliver [SRC-46][SRC-55] | Points allowed per 100 possessions | (Opponent PTS / Opponent Possessions) × 100 [SRC-55][SRC-77] | 85-90% | Tier 2 | SRC-46, SRC-48, SRC-51, SRC-55, SRC-77 |
| **Net Rating** | Derived [SRC-55][SRC-77] | Point differential per 100 possessions | ORtg - DRtg [SRC-55][SRC-77] | 90-95% | Tier 1 | SRC-55, SRC-56, SRC-77 |
| **Pace** | Various [SRC-2][SRC-15] | Possessions per 48 minutes | (FGA + 0.44 × FTA + TOV) × (48 / MIN) [SRC-2][SRC-15] | 95%+ | Tier 1 | SRC-2, SRC-15, SRC-48, SRC-51 |

### Four Factors (Offense & Defense)

| Metric | Developer | Aspect Covered | Weight | Formula | Reliability | Tier | Source IDs |
|--------|-----------|----------------|--------|---------|-------------|------|------------|
| **Effective FG% (eFG%)** | Dean Oliver [SRC-46][SRC-49] | Shooting efficiency (3PT adjustment) | 40% | (FGM + 0.5 × 3PM) / FGA [SRC-1][SRC-49] | 85-90% | Tier 2 | SRC-1, SRC-46, SRC-49, SRC-57, SRC-75 |
| **Turnover Rate (TOV%)** | Dean Oliver [SRC-46][SRC-49] | Possessions ending in turnover | 25% | TOV / (FGA + 0.44 × FTA + TOV) [SRC-1][SRC-49] | 80-85% | Tier 2 | SRC-1, SRC-46, SRC-49, SRC-75 |
| **Offensive Rebound% (OREB%)** | Dean Oliver [SRC-46][SRC-49] | Percentage of offensive rebounds | 20% | OREB / (OREB + Opp DREB) [SRC-1][SRC-49] | 80-85% | Tier 2 | SRC-1, SRC-46, SRC-49, SRC-75 |
| **Free Throw Rate (FTR)** | Dean Oliver [SRC-46][SRC-49] | Free throws per field goal attempt | 15% | FTA / FGA [SRC-1][SRC-49] | 75-80% | Tier 2 | SRC-1, SRC-46, SRC-49, SRC-75 |

**Note:** The Four Factors explain ~95% of variance in offensive efficiency [SRC-46][SRC-77]. Net Four Factor Rating (team FF rating - opponent FF rating) is highly predictive of team success [SRC-56][SRC-75].

### Team Impact Metrics

| Metric | Developer | Aspect Covered | Key Formula Elements | Reliability | Tier | Source IDs |
|--------|-----------|----------------|---------------------|-------------|------|------------|
| **Team PIE** | NBA Stats [SRC-1] | Percentage of game events achieved | Same as player PIE, aggregated [SRC-1] | R² = 0.908 with win% | Tier 1 | SRC-1 |
| **Adjusted Efficiency Differential** | Various [SRC-14] | Point differential adjusted for opponent | Team margin - opponent margin [SRC-14] | 90-95% | Tier 1 | SRC-14 |
| **Simple Rating System (SRS)** | Various [SRC-36] | Point differential adjusted for schedule | Margin + opponent SRS [SRC-36] | 85-90% | Tier 2 | SRC-36, SRC-67 |

---

## Source Mapping

All metrics reference source IDs (SRC-X) that correspond to entries in `nba_metrics_sources.md`.