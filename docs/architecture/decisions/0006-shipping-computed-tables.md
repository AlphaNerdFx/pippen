# ADR 0006: The wheel ships computed tables, under a size-capped exemption

- Status: Accepted
- Date: 2026-09-16
- Deciders: AlphaNerdFx

## Context

Phase 4's exit condition is that `pip install pippen` gives a working metric.
The obvious reading of "metric" is a number a user can obtain, not a library
that could compute one given inputs they do not have.

Rebuilding those numbers is not a small ask. Possession data comes from
data.nba.com at one request per second by compliance rule, 11,070 games across
the covered seasons, roughly three and a half hours before any computation
starts. The stint extraction adds about an hour and the ridge solve a few
minutes per window. An install whose first useful action is a four-hour download
would fail the exit condition in substance while passing it in form.

This collides with non-negotiable rule 1 in `CLAUDE.md`: data never enters git,
enforced by `scripts/hooks/no_data_commits.py`, which refuses any staged file
with a Parquet, CSV or similar suffix.

### What the rule was protecting against

The rule exists because a Parquet file committed once stays in history forever
and cannot be removed without rewriting it. The concrete risk is the 530 MB of
raw play-by-play and 1.5 GB of possession data in `data/raw/`, which would make
the repository unusable to clone.

The tables in question are a different size and a different kind of thing:

| File | Rows | Bytes |
|---|---|---|
| `rapm_ratings.parquet` | 5,427 | 227,822 |
| `metric_reliability.parquet` | 750 | 42,049 |

A rating is one row per player per three-season window. The millions of
possessions behind it stay out.

### Alternatives considered

**Ship code only, users fetch their own data.** Honest, and fails the exit
condition. It also puts a four-hour, rate-limited download between a curious
reader and any output, which for a research package is the difference between
being evaluated and being closed.

**Fetch the tables at first use from a GitHub release.** Keeps git clean, and
adds a network dependency to the first call, breaks in offline and air-gapped
environments, and introduces a failure mode where the package and the data it
downloads are different versions. It also needs the release to exist before the
package works, which inverts the dependency between publishing and installing.

**Generate the tables during the build.** Impossible. A CI runner cannot spend
four hours on rate-limited requests for every build, and `uv build` runs on a
machine with no data at all.

## Decision

The computed tables live in `src/pippen/_data/` and travel inside the wheel and
the sdist. `src/pippen/published.py` reads them through
`importlib.resources.files`, so they are found through the loader that imported
the package rather than by arithmetic on `__file__`.

Rule 1 gains one exemption, and every exemption in the hook gains a size cap:

```python
ALLOWED_PREFIXES: Final = {
    "tests/fixtures/": 256 * 1024,
    "docs/": 256 * 1024,
    "src/pippen/_data/": 1024 * 1024,
}
```

The cap is what keeps the exemption narrow. A directory allowed to hold a 40 KiB
reference table should not quietly become where someone puts a season of
play-by-play, and an exemption without a bound is an invitation to do exactly
that. The two pre-existing prefixes were previously uncapped and are now capped
as well.

Only derived values go in. `docs/guides/licensing.md` marks values computed in
this repository as publishable, and the raw responses that produced them as not.
RAPM comes from data.nba.com possessions, where derived features may be
published and raw responses may not. The reliability table comes from hoopR
under CC BY 4.0, which carries attribution rather than restriction.

## Consequences

**Gained: the exit condition is met in substance.** Verified from a clean
virtualenv outside the repository with no data directory: `pippen.rapm_ratings`
returns 335 players above 8,000 possessions for the 2022-24 window, led by
Jokić at 9.97 points per 100.

**Gained: the numbers in the documentation are checkable by a reader.** A
claim about measured reliability that requires four hours of setup to verify is
one nobody verifies.

**Accepted: the tables are now part of the public API.** Changing a column name
in `rapm_ratings.parquet` breaks callers as surely as changing a function
signature, and it happens through a data file rather than through code, where it
is easier to do carelessly. `tests/unit/test_published.py` pins the column set
and the headline reliability ordering for that reason.

**Accepted: the repository grows by about 270 KB per regeneration, forever.**
Regenerating on every release would accumulate. The tables are regenerated when
the underlying method changes rather than on a schedule.

**Accepted: shipped numbers go stale.** The bundled RAPM covers NBA 2016-17
through 2024-25 because that is what the upstream feed serves, and a user
installing in 2028 gets 2024 numbers unless they rebuild. `FIRST_RAPM_SEASON`
and `LAST_RAPM_SEASON` are exported so a caller can check rather than assume.
