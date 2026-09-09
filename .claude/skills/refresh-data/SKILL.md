---
name: refresh-data
description: Refresh the NBA data cache from upstream sources and re-run validation. Use when the user asks to update, re-download, or refresh data, when a new season's games have been played, or when validation is failing and you need a clean copy of the raw inputs.
---

# Refresh the data cache

Bring `data/raw/` up to date and confirm the result is usable before anything
downstream runs.

## Order of operations

Do not reorder these. Validation before processing is the point.

1. **Bulk history from hoopR.** One Parquet per season, direct download. Seasons
   before the current one rarely change, so skip any already present unless the
   user asked for a full refresh.

   ```bash
   uv run nba-impact fetch --seasons 2002-2025
   ```

2. **Current season from the NBA stats endpoints.** This one always refetches,
   because games are still being played.

   ```bash
   uv run nba-impact fetch --seasons 2026 --force
   ```

   Respect the rate limit. One request per second, no exceptions. Exceeding it
   gets the endpoint blocked for everyone, not just for us.

3. **Validate before using anything.**

   ```bash
   uv run nba-impact validate --seasons 2002-2026
   ```

## What validation checks

- Every scheduled game appears in the play-by-play.
- No duplicate game and player rows.
- Play-by-play aggregates reconcile to box score totals.
- Event timestamps run in order within each period.
- No rows dated after the season's end.

## When validation fails

Do not patch files in `data/raw/`. Raw is immutable by design. Redownload the
affected season instead:

```bash
uv run nba-impact fetch --seasons 2019 --force
```

If it fails again on the same season, the upstream file is the problem. Record
which games are affected in the issue, and exclude that season rather than
silently working around it.

## Never

- Never commit anything from `data/`. The pre-commit hook blocks it and the hook
  is correct.
- Never raise the rate limit to make a download finish sooner.
