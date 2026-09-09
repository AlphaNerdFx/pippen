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
