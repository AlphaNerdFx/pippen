# PIPPEN

**Player Impact from Pooled Priors and Estimated Noise.**

Reliability-adjusted NBA player impact estimates, with calibrated uncertainty.

[![CI](https://github.com/AlphaNerdFx/pippen/actions/workflows/ci.yml/badge.svg)](https://github.com/AlphaNerdFx/pippen/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org)

[![PyPI](https://img.shields.io/pypi/v/pippen.svg)](https://pypi.org/project/pippen/)

> **Status: 0.1.0, and the central claim has been answered.** RAPM is computed
> and validated, metric reliability is measured across 25 seasons, and both
> ship inside the wheel. The fused rating does not beat RAPM alone and is not
> distinguishable from it. That result is published in
> [the claim under test](https://alphanerdfx.github.io/pippen/methodology/claim-under-test/)
> rather than omitted. The API is 0.x and may still change.

---

## What this is

Public NBA impact metrics disagree with each other, and none of them tells you how
much to trust any single number. This project treats the existing metrics as
**noisy measurements of one quantity that nobody observes directly**: a player's
true contribution to point differential.

That reframing turns player evaluation into a measurement-error problem, which
statistics has known how to solve for a century. The pipeline:

1. Compute **RAPM** (Regularized Adjusted Plus-Minus) from possession-level
   play-by-play, so the project owns its own ground truth rather than borrowing
   a paywalled one.
2. **Measure** how reliable each input metric actually is, by splitting each
   player's season into odd and even games and correlating the halves.
3. **Fuse** the metrics by inverse-variance weighting, so noisier measurements
   count for less.
4. Report the result as a value **and an interval**, because a rookie with 200
   minutes and a starter with 2,400 minutes should not be quoted with the same
   confidence.

Scottie Pippen is the point of the name. He is the canonical player whose box
score understated what he did, and whose value showed up in what happened to the
team when he played. That gap is the thing this project measures.

## What this is not

- **Not a betting tool.** No odds, no spreads, no bankroll advice.
- **Not a replacement for DARKO or EPM.** Those are excellent and this project
  measures itself against them rather than claiming to beat them.
- **Not a redistribution of anyone's paid data.** See [Data and licensing](#data-and-licensing).
- **Not validated yet.** The headline claim below is a hypothesis under test, not
  a result.

## The claim under test

> Does PIPPEN predict next-season team net rating better than any single input
> metric does, out of sample?

If the answer is no, the fusion added nothing, and this README will say so.
Stating a falsifiable claim before running the experiment is the point.

---

## Installation

```bash
pip install pippen
```

Development install, using [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/AlphaNerdFx/pippen
cd pippen
uv sync --extra dev
uv run pippen --help
```

Optional extras: `sources` (data downloaders), `fit` (model fitting), `api`,
`dashboard`, `docs`.

## Quickstart

```bash
pippen paths                              # where data will be cached
pippen fetch  --seasons 2015-2024         # download play-by-play and box scores
pippen rapm   --seasons 2015-2024 --window 3
pippen train
pippen evaluate                           # runs the claim under test
```

---

## Data and licensing

The code is **Apache-2.0**. Published data artifacts are **CC BY 4.0**.

The rule this project follows without exception:

> **If a value was not computed from a source that permits redistribution, it does
> not go into a release.**

| Input | Source | Position |
|---|---|---|
| RAPM (own) | Computed from possession data | Ours. Published. |
| Four Factors, Net Rating, box-score rates | [hoopR-nba-data](https://github.com/sportsdataverse/hoopR-nba-data), CC BY 4.0 | Published, with attribution. |
| Tracking features | `nba_api` | Derived features only. Raw responses are never redistributed. |
| BPM, VORP, Win Shares | Basketball-Reference | **Local validation only.** Never in a release artifact. |
| EPM, DARKO | Dunks & Threes, darko.app | **Not used.** Paywalled or unlicensed. Compared by rank correlation only. |

NBA data carries usage restrictions. This project is for personal and research
use. Commercial use of the underlying league data requires licensing from the
rights holders, which this project does not grant and cannot grant.

### Attribution

Bulk historical play-by-play comes from **hoopR-nba-data** by the
SportsDataverse authors, used under CC BY 4.0. Possession and lineup
reconstruction uses **[pbpstats](https://github.com/dblackrun/pbpstats)** by
Darryl Blackport, MIT licensed.

---

## Documentation

Full documentation, including the method write-up and its limitations, lives at
<https://alphanerdfx.github.io/pippen/>.

- [Method](docs/methodology/). How reliability is measured and how fusion works.
- [Architecture](docs/architecture/). Pipeline stages and data layout.
- [Research notes](docs/research/). The background survey this project grew from.

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), and note
that this project ships a [Code of Conduct](CODE_OF_CONDUCT.md).

## Releasing

Publishing uses [Trusted Publishing](https://docs.pypi.org/trusted-publishers/),
so no PyPI token is stored in this repository or in GitHub's secret store.
`.github/workflows/release.yml` proves the workflow's identity to PyPI through a
short-lived OpenID Connect token instead.

The one-time browser setup, plus tagging a release, is scripted:

```bash
./scripts/setup_publishing.sh
```

It is resumable, so a run that stops halfway picks up where it left off, and it
refuses to tag a dirty working tree.

## License

Apache License 2.0. See [LICENSE](LICENSE).
