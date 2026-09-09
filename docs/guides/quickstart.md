# Quickstart

```bash
nba-impact paths                              # where data will be cached
nba-impact fetch  --seasons 2015-2024         # download play-by-play and box scores
nba-impact rapm   --seasons 2015-2024 --window 3
nba-impact train
nba-impact evaluate
```

!!! warning "Not implemented yet"
    Only `paths` and `version` work today. The rest report which week of the
    implementation plan they land in.

## What each step does

**`fetch`** downloads bulk history from the hoopR data repository as Parquet, one
file per season, and the current season from the NBA stats endpoints. Bulk
history is a download rather than a scrape, so it takes minutes rather than
weeks.

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
export NBA_IMPACT_DATA_DIR=/mnt/big-disk/nba
nba-impact paths
```

Expect roughly 500 MB for 2002 through 2026 of play-by-play.
