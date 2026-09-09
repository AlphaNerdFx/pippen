# Pipeline

```
        ┌──────────────┐   ┌──────────────┐
sources │ hoopR bulk   │   │ NBA stats    │
        │ Parquet      │   │ endpoints    │
        │ CC BY 4.0    │   │ 1 req/sec    │
        └──────┬───────┘   └──────┬───────┘
               │                  │
               └────────┬─────────┘
                        ▼
                 ┌─────────────┐
   raw/          │  download   │  immutable, never edited
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │  validate   │  pandera schemas + reconciliation
                 └──────┬──────┘
                        ▼
   interim/      ┌─────────────┐
                 │ possessions │  pbpstats: stints and on-court lineups
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │    RAPM     │  sparse ridge, cross-validated lambda
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │ reliability │  odd/even split, Spearman-Brown
                 └──────┬──────┘
                        ▼
   processed/    ┌─────────────┐
                 │   fusion    │  NumPyro hierarchical measurement model
                 └──────┬──────┘
                        ▼
              ┌─────────┴─────────┐
              ▼         ▼         ▼
          dataset    package    API +
          release    on PyPI    dashboard
```

## Stage responsibilities

| Stage | Module | Output |
|---|---|---|
| Download | `nba_impact.data.hoopr`, `nba_impact.data.nba_api` | `raw/` Parquet |
| Validate | `nba_impact.data.validate` | pass or fail, with a report |
| Possessions | `nba_impact.rapm.possessions` | stints with lineups |
| Design matrix | `nba_impact.rapm.design` | sparse matrix |
| Solve | `nba_impact.rapm.ridge` | coefficients with standard errors |
| Reliability | `nba_impact.reliability.testretest` | one coefficient per metric |
| Fusion | `nba_impact.model.fusion` | RAIM with intervals |

## Why files rather than a database

A database server needs hosting, and this project has no budget for hosting.
DuckDB runs SQL directly against Parquet files with no server at all, and handles
the stint aggregation faster than a small Postgres instance would. If the project
ever needs concurrent writers, that changes. It does not need them today.

## Orchestration

GitHub Actions on a schedule, not Airflow. Airflow solves dependency graphs across
many teams and machines. This pipeline is a line, it runs once a day in season,
and a cron trigger in a workflow file is the whole of it.
