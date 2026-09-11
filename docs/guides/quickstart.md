# Quickstart

```bash
pippen paths                                    # where data will be cached
pippen fetch    --seasons 2024                  # play-by-play for one season
pippen fetch    --seasons 2024 --dataset player_box
pippen fetch    --seasons 2024 --dataset team_box
pippen fetch    --seasons 2024 --dataset schedules
pippen validate --seasons 2024                  # check the tables against each other
pippen rapm     --seasons 2015-2024 --window 3
pippen train
pippen evaluate
```

!!! warning "Partly implemented"
    `paths`, `fetch` and `validate` work. `rapm`, `train` and `evaluate` report
    which phase of the roadmap they land in.

A worked run on the 2024 season, which is what the four fetches above produce:

```
7 checks: 7 passed
   schedule_and_play_by_play_agree: all 1320 completed games have events, 2 not played
   teams_match_the_schedule: teams agree across 1320 games
   events_run_in_order: periods are non-decreasing within every game
   dates_fall_inside_the_season: all dates fall within 2023-08-01 to 2024-09-30
   no_duplicate_rows_schedules: 1322 rows, all unique on ['game_id']
   no_duplicate_rows_player_box: 35028 rows, all unique on ['game_id', 'athlete_id']
   no_duplicate_rows_team_box: 2640 rows, all unique on ['game_id', 'team_id']
```

The two games not played were postponed. `validate` exits non-zero if any check
fails, so it can gate a scheduled refresh.

## What each step does

**`fetch`** downloads from the hoopR data repository as Parquet. Bulk history is
a download rather than a scrape, so it takes minutes rather than weeks.

Most tables are published one file per season. The schedule is not: it is a
single table covering 2002 to 2027, so `fetch --dataset schedules` downloads it
once and ignores the season range. `validate` filters it per season.

**`validate`** checks the downloaded tables against each other. A file can be
perfectly well formed and still disagree with the file next to it.

**`rapm`** reconstructs which five players were on the floor for each stretch of
play, computes point margin per 100 possessions for each stretch, and solves a
ridge regression with one coefficient per player. `--window 3` pools three
seasons, because single-season estimates are too noisy to act on.

**`train`** measures how reliable each input metric is, then fits the
measurement model that fuses them.

**`evaluate`** runs the claim under test and prints the comparison table.

## Where data goes

By default, a `data/` directory beside the repository. Override it:

```bash
export PIPPEN_DATA_DIR=/mnt/big-disk/nba
pippen paths
```

Expect roughly 500 MB for 2002 through 2026 of play-by-play.
