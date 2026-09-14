# Upstream data quirks

Facts about the hoopR box scores as published, verified against the 25 seasons in
`data/raw/`. None of these are errors in this project's code. All of them will
produce wrong numbers if the obvious filter is used instead of the one recorded
here.

## `season_type == 2` includes the All-Star Game

hoopR labels the All-Star exhibition as regular season. It appears in 14 of the
25 seasons under pseudo-teams whose abbreviations change format almost every
year: `EAST`, `WEST`, `LEB`, `STE`, `GIA`, `DUR`, `WORLD`, `USA`, `CHK`, `SHQ`,
`KEN`, `CAN`, `STARS`, `STRIPES`.

That is 479 player rows of exhibition basketball, and it lands on precisely the
players whose season metrics matter most.

| Seasons affected | Pseudo-team rows |
|---|---|
| 2013-2017 | 24 to 25 per season, two teams |
| 2018-2020 | 44 to 48 per season, four teams |
| 2021-2024 | 22 to 24 per season, two teams |
| 2025-2026 | 52 and 73, four and three teams |

A hardcoded list of abbreviations is not a fix, since the format changed in 2018,
2021, 2025 and 2026. The stable rule is structural:

> Keep only games whose two participating teams each appear in 40 or more games
> that season.

Every real team plays at least 66. Every pseudo-team plays at most 3. The rule
excludes them by construction and needs no maintenance.

## The NBA Cup final is also `season_type == 2`

In 2024 the Lakers and Pacers each show 83 regular-season games. The extra one is
the in-season tournament final, which ESPN counts here and the NBA does not count
in official standings. The same holds for 2025 and 2026, where the maximum team
game count is 83.

This is a real game between real teams under regular-season rules. It is kept.
The consequence to remember is that a team's regular-season game count is not
always 82, so anything that divides by 82 rather than by observed games is wrong
for two teams per season from 2024 onward.

## Play-in games are `season_type == 5`

Six games in 2024, between April 16 and 19. They are excluded from
reliability work because opponent quality is not random in them.

## `plus_minus` is unusable before 2009 and incomplete after

| Seasons | Rows where `plus_minus` parses as a number |
|---|---|
| 2002-2008 | 0% |
| 2009-2012 | 70% to 73% |
| 2013-2026 | 80% to 85% |

The column is typed as `object`, not numeric, and carries non-numeric values that
`pd.to_numeric` rejects. Any plus-minus-derived quantity is restricted to 2009
onward with roughly a fifth of rows dropped, and cannot be part of a metric that
claims 25-season coverage.

## Season lengths are not all 82 games

| Season | Games per team | Cause |
|---|---|---|
| 2012 | 66 | Lockout |
| 2020 | 75 | COVID-19 suspension |
| 2021 | 72 | Shortened schedule |
| 2024-2026 | 83 for two teams | NBA Cup final |

Anything that assumes a half-season is 41 games is wrong for four of the 25
seasons. Carry the observed game count rather than assuming one.

## The two sources label seasons differently

hoopR names a season by the year it ends. The NBA names it by the year it
starts. They are one apart, and both numbers look equally plausible on a file
name.

| Season | hoopR file | NBA game id prefix | data.nba.com path |
|---|---|---|---|
| 2015-16 | `team_box_2016.parquet` | `00215` | `/nba/2015/` |
| 2016-17 | `team_box_2017.parquet` | `00216` | `/nba/2016/` |
| 2023-24 | `team_box_2024.parquet` | `00223` | `/nba/2023/` |

Verified by reading the dates: hoopR's 2016 regular season runs 2015-10-27 to
2016-04-13, and its 2017 runs 2016-10-25 to 2017-04-12.

Every join between a RAPM rating and a box-score metric crosses this boundary.
Getting it wrong shifts a player's inputs by a full year, the join still
matches, the row counts still look right, and the model learns from the wrong
season. `pippen.seasons` exists so the conversion is applied by name rather
than remembered, and so a reader can tell which convention a number is in.

## Play-by-play with lineups covers fewer seasons than the box scores

The box scores cover 2002 to 2026 in hoopR labelling. Play-by-play carrying
on-court lineups, which is what RAPM needs, covers far less.

| Route | Seasons served | Notes |
|---|---|---|
| `stats.nba.com/stats/playbyplayv2` | none | Answers HTTP 200 with the body `{}` for every game of every season. This is the endpoint `pbpstats` calls. |
| `data.nba.com` mobile_teams | NBA 2016 to 2024 | What this project uses. 2015 and earlier return HTTP 403; 2025 onward return a stub with an empty period array. |
| `stats.nba.com/stats/playbyplayv3` | NBA 2015 to 2025 | Alive, but drops the numeric event codes and carries one `personId` per action, so a substitution no longer names both players. Using it means rewriting `pbpstats`' substitution tracking. |

So RAPM covers nine seasons, NBA 2016-17 through 2024-25, which is hoopR 2017
through 2025.

Two further details on that feed:

- The raw `ord` key, which `pbpstats` reads to order simultaneous events,
  appears only from 2023-24. Without it every pre-2023 game raises
  `AttributeError: 'DataRebound' object has no attribute 'order'`. The value is
  the event's index in feed order, so it is reconstructed from `period` and
  `evt` rather than worked around.
- About 2.7 percent of games raise `EventOrderError`, where a rebound does not
  follow a missed shot. `pbpstats` ships a repair for this on its `stats_nba`
  path and not on this one. Those games are recorded and skipped.

## data.nba.com rejects a User-Agent containing a URL

No `User-Agent` gives HTTP 403. A `User-Agent` carrying a URL also gives 403,
which rules out the usual `pippen/0.1 (+https://github.com/...)` convention.

| Sent | Result |
|---|---|
| nothing | 403 |
| `pippen/0.1 (+https://github.com/AlphaNerdFx/pippen)` | 403 |
| `Mozilla/5.0 (Windows NT 10.0; Win64; x64)` | 200 |
| `Mozilla/5.0 (Windows NT 10.0; Win64; x64) pippen/0.1` | 200 |
| `Mozilla/5.0 (Windows NT 10.0; Win64; x64) (+https://github.com/...)` | 403 |

The default keeps the browser-shaped prefix the filter requires and appends the
package name and version, so the traffic stays identifiable.

## ESPN and NBA team abbreviations differ on six teams

Twenty-four of thirty agree. These do not, and any join on team abbreviation
across the two sources has to map them.

| NBA | ESPN |
|---|---|
| GSW | GS |
| NOP | NO |
| NYK | NY |
| SAS | SA |
| UTA | UTAH |
| WAS | WSH |

ESPN additionally emits `EAST` and `WEST` for the All-Star Game, which the
team-games rule above already excludes.
