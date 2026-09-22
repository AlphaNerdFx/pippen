# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries below the `Unreleased` heading are generated from
[Conventional Commits](https://www.conventionalcommits.org/) at release time.

## [Unreleased]

## [1.0.0] - 2026-09-22

First public release. 0.1.0 was prepared and never published, so everything
below ships at once.

### Added

- Project foundation: packaging, linting, static typing, tests, continuous
  integration, documentation scaffold, and contributor governance.
- `pippen.paths` module resolving the on-disk data layout.
- `pippen` command-line interface.
- Data layer: hoopR bulk Parquet downloads, a rate-limited NBA stats client,
  pandera schemas, and four families of validation.
- The possession coefficient measured per season from play-by-play rather than
  hard-coded at 0.44. Every one of 25 seasons came out below the convention,
  pooling at 0.4178.
- RAPM from data.nba.com possessions for NBA 2016-17 through 2024-25, validated
  at Spearman 0.914 against an independently built stint dataset.
- Split-half reliability of 15 box-score metrics, measured across 25 seasons
  with a Spearman-Brown correction.
- A NumPyro measurement-error model, ridge and tuned LightGBM baselines, SHAP
  attributions, and an interval calibration check at 90.9 percent against a
  nominal 90.
- Public API frozen at six names, with the computed tables shipped inside the
  wheel so `pip install pippen` needs no download.
- `first_season`, `last_season` and `seasons_played` on the ratings table,
  naming the seasons a player actually recorded a possession in. 2,994 of the
  5,427 rows cover fewer than the window's three seasons, so the window alone
  overstates the evidence behind more than half the table.
- HTTP service over the shipped tables, with a two-stage non-root container and
  a KServe manifest validated against the CRD schema.
- Streamlit dashboard: player lookup, comparison, measured reliability, and a
  page stating what the metric cannot tell you.
- Distribution drift report, generated into the docs at build time.
- Model card following Mitchell et al. 2019.

### Findings published

- **The claim under test is answered, and the answer is no.** Fusing public
  metrics weighted by reliability does not predict next-season team net rating
  better than RAPM alone, and is not distinguishable from it (p = 0.171).
- Reliability runs against validity: across this metric set it correlates
  -0.564 with correlation against RAPM. Nothing here turns reliability into a
  weight.
- A one-factor model of box-score metrics recovers player position rather than
  impact.

### Not included, deliberately

- **No per-player interval.** The only candidate was a bootstrap standard error
  on a ridge coefficient, and it rises with possessions rather than falling.
  `possessions` is the precision signal instead. See ADR 0007.
- EPM and DARKO. One is paywalled, the other states no licence. Neither enters
  a published artifact.
- PER, DBPM and unregularised APM, excluded on measured reliability.

### Known limitations at this release

- Three of 5,427 shipped rating rows carry a null player name, where the ESPN to
  NBA crosswalk failed. All three sit under 20 possessions.
- `metric_reliability.parquet` ships no per-metric correlation against RAPM, so
  the -0.564 finding is stated rather than plotted.
- `import pippen` needs pandas and pyarrow, but scipy, scikit-learn, pandera,
  typer and rich are core dependencies, so an install is heavier than the public
  API requires. Narrowing this is a breaking change and is deferred.
