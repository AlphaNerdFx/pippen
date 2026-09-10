# Data layout

Data never enters git history. It is cached locally and distributed through
releases.

```
$PIPPEN_DATA_DIR/
├── raw/          unmodified downloads, exactly as retrieved
├── interim/      intermediate tables produced during processing
├── processed/    analysis-ready tables, published in dataset releases
└── sources/      archived bibliography
```

The root is resolved in this order:

1. the `PIPPEN_DATA_DIR` environment variable;
2. a `data/` directory beside the repository root, when running from a checkout;
3. the platform user-cache directory, for installed copies.

## Why the stages are separate

**`raw` is never edited.** If a download is wrong, the fix is to download it
again, not to patch it in place. Keeping raw immutable means any bug in
processing can be traced by re-running from the same inputs.

**`interim` is disposable.** Anything here can be rebuilt from `raw`. It is
excluded from releases.

**`processed` is what gets published**, and only values whose licences permit
redistribution reach it. See [data licensing](licensing.md).

## File naming

```
<stage>/<dataset>/<dataset>_<season>.parquet
```

`season` is the end year, so the 2023-24 season is `2024`. Resolve a path in
code with:

```python
from pippen.paths import season_file

path = season_file("raw", "play_by_play", 2024)
```

## Why Parquet rather than CSV

Parquet stores columns rather than rows and compresses each one. Reading three
columns out of two hundred reads only those three. For play-by-play, which is
wide and long, this is the difference between a query taking a second and taking
a minute.

## What validation runs

Two layers run before anything computes a number, and they catch different
things.

**Shape validation** (`pippen.data.schemas`) sees one table. It checks that
required columns exist, coerces dtypes so two seasons cannot disagree about
whether an identifier is 32 or 64 bits, and enforces per-row constraints such
as a percentage lying between 0 and 1.

**Dataset validation** (`pippen.data.validate`) sees several tables at once and
checks what only exists between them. A play-by-play file missing forty games
is perfectly valid on its own terms. Every column is present, every dtype is
right, every row passes. The only thing wrong with it is that the schedule
disagrees.

| Check | Catches |
|---|---|
| Schedule and play-by-play agree | Missing games, or events from a different season |
| Teams match the schedule | A fixture recorded two different ways, so possessions land on the wrong side |
| No duplicate rows | A re-download concatenated on top of itself |
| Events run in order | Two games merged under one identifier, or a file sorted by something other than time |
| Dates fall inside the season | A year and season mix-up, or a filename off by one |

Run them for one season:

```python
from pippen.data import validate

results = validate.validate_season(2024, tables)
print(validate.summarise(results))
```

### Passed, failed and skipped are three outcomes

A check that could not run because an input was absent reports `skipped`, never
`passed`. This distinction is the point rather than a detail. A skip that
reported as a pass would produce a green validation report for data nobody
checked, which is worse than having no report at all. `CheckResult.ok` is true
only for `passed`, so a skip cannot be mistaken for a clean result by anything
downstream either.

### The season window is deliberately wide

A season labelled by its end year runs from roughly October of the previous
calendar year to June of the labelled one. The window used for the date check
runs from 1 August to 30 September, which is wider than any real schedule. It
exists to catch a year and season mix-up, not to police the exact first and
last day of a calendar that moves with lockouts, pandemics and mid-season
tournaments.
