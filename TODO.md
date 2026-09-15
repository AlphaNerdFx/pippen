# Roadmap

Phases are gated by outcomes, not by dates. Each one declares what must be true
before it starts, what must be true before it is finished, and what actually
limits it. The reasoning is in
[ADR 0002](docs/architecture/decisions/0002-outcome-gated-phases.md).

## How to read the limit column

| Limit | Meaning | Do more agents help? |
|---|---|---|
| Agent-parallel | Well specified, verifiable, splits across files | Yes, substantially |
| Network-bound | Capped by a rate limit we chose to honour | No |
| Compute-bound | CPU time on a fixed algorithm | No, only better algorithms |
| Judgement | Needs a decision from the maintainer | No |
| Review-bound | Capped by how fast one person can check the output | No, they make it worse |

---

## Phase 0: Foundation

Status: complete. Took 13 hours and 18 commits.

Entry: none.
Done when: the repository is public, three workflows pass on a real runner, the
docs site is live, and the package name is reserved.
Limit: agent-parallel.

- [x] `git init`, Apache-2.0 licence, `.gitignore` that blocks data
- [x] `pyproject.toml` with uv, ruff, mypy strict, pytest
- [x] Pre-commit hooks, including a hook that blocks committing data
- [x] CI: lint, types, tests on Python 3.10 to 3.13, build, docs
- [x] Release workflow using PyPI Trusted Publishing
- [x] Governance: contributing, code of conduct, security policy, templates
- [x] Docs site scaffold, building in strict mode
- [x] `pippen.paths` and the CLI skeleton
- [x] Bibliography archiver
- [x] Rigour pipeline: mutation testing, benchmarks, determinism, lockfile drift
- [x] Named PIPPEN; Dependabot automation off so every commit has a human author
- [x] Push to GitHub, enable Pages and Discussions, disable the wiki
- [x] Get all three workflows green on a real runner
- [x] Enable private vulnerability reporting and Dependabot alerts
- [x] Reserve the `pippen` name on PyPI (0.0.0, name reservation only)
- [x] Audit the source research and record every contradiction in an errata
- [x] Writing, explanation, scope and orchestration rules in CLAUDE.md

---

## Phase 1: Data layer

Ships: dataset v0.

Entry: Phase 0 complete.
Done when: a clean checkout can run one command and end up with validated
play-by-play and box scores on disk for 2015 to 2024, with every table passing
its schema and every game in the schedule accounted for.
Limit: mixed. The code is agent-parallel. The hoopR bulk download is a direct
file fetch and takes minutes. The NBA stats client is network-bound at one
request per second.

- [x] hoopR bulk Parquet downloader, 2002 to present
- [x] NBA stats client with rate limiting and backoff
- [x] pandera schemas for every table
- [x] Validation: completeness, consistency, accuracy, temporal integrity
- [x] Nightly refresh workflow
- [x] Measure the possession coefficient per season instead of hard-coding 0.44
- [x] Save the browser-only citations by hand (16 archived)
- [x] Record every broken citation in `docs/methodology/errata.md`

  The original wording said "replace or remove" the broken citations. That is not
  possible: `docs/research/` is a protected record and is never edited. The errata
  page is the resolution, and it names each dead source and what it used to support.

---

## Phase 2: RAPM

Ships: a validation report.

Entry: Phase 1 done, with possession-level data on disk.
Done when: computed multi-season RAPM reaches Spearman correlation above 0.85
against an independent build, possession totals reconcile exactly against an
independent box score, and RAPM split-half reliability rises with window length.

Two criteria changed during Phase 2 and both changes are recorded in
`docs/methodology/rapm-validation.md`. The comparison target moved from a
published RAPM, which exists only as unlicensed web tables, to an independently
built stint dataset run through this project's own solver, which isolates the
lineup reconstruction instead of confounding it with someone else's modelling
choices. And bootstrap standard errors were replaced, because measured, they
track ridge shrinkage rather than information: within a window they rise with a
player's possessions.
Limit: network-bound to fetch possessions, then compute-bound for the solve,
then judgement at the gate.

- [x] Possession and stint extraction via pbpstats
- [x] Sparse design matrix builder
- [x] Ridge solver, cross-validated lambda, multi-season windows
- [x] Bootstrap standard errors
- [x] Property tests: possessions reconcile, five a side, order invariance
- [x] Decision gate: Spearman 0.914 against an independent stint build

### Decisions settled before Phase 2 starts

**If the gate fails**, debugging gets a fixed budget of one week, then the target
switches to next-season team net rating, which needs no external reference. An
unbounded debug on a gate has no exit condition, which is the same failure as a
polling loop. The discrepancy analysis is published either way, as a reference
point for anyone computing RAPM from the same sources.

**Scope of the first run** is NBA 2016 through 2024, nine seasons, pooled into
multi-season windows. Ten was planned; data.nba.com does not serve 2015. See
`docs/methodology/data-quirks.md`. That still clears the gate's statistical
requirement and costs about 3.4 hours of rate-limited fetching. Older seasons stay unfetched until there
is a reason beyond completeness, and if that reason arrives they get pooled into
multi-year windows rather than published as single seasons. Single-season RAPM
is what this project's own research calls too noisy to act on, so publishing it
would invite the criticism the project exists to avoid.

**The two data paths are not the same cost.** hoopR bulk Parquet is a direct file
download and covers 25 seasons in minutes. Possession data with on-court lineups
comes from the NBA API at one request per second and costs hours. Only RAPM needs
the slow path. The possession coefficient, the Four Factors and everything
box-score-derived come from the fast one.

---

## Phase 3: The measurement model

Entry: Phase 2 gate passed, or the fallback target agreed.
Done when: the claim under test has been run out of sample and the answer is
published either way, and the credible intervals are calibrated so that roughly
90 percent of held-out values land inside the 90 percent interval.
Limit: compute-bound for fitting, judgement for the result.

- [x] Fetch all 25 hoopR seasons and measure the possession coefficient per season
- [x] Split-half reliability with Spearman-Brown correction
- [x] NumPyro hierarchical fusion model
- [x] LightGBM and ridge baselines, tuned with Optuna, tracked in MLflow
- [x] SHAP attributions
- [x] Interval calibration check (90.9% at nominal 90%)
- [x] Run the claim under test and publish the answer either way (answer: no)

The claim: does PIPPEN predict next-season team net rating better than any single
input metric does, out of sample? A negative answer is a result and gets
published as one.

---

## Phase 4: Package

Ships: v0.1.0 on PyPI.

Entry: Phase 3 has produced numbers worth installing.
Done when: `pip install pippen` gives a working metric, and the release was
published by the workflow rather than by hand.
Limit: agent-parallel, with one manual step that cannot be automated.

- [ ] Freeze the public API, complete docstrings
- [ ] Configure Trusted Publishing on PyPI (manual, needs the maintainer's login)
- [ ] Zenodo integration for a citable DOI

---

## Phase 5: Serving

Ships: a live endpoint.

Entry: Phase 4 released.
Done when: a public URL returns a player's estimate with its interval, and the
container image builds from a clean checkout.
Limit: agent-parallel, with a manual deployment step.

- [ ] FastAPI service with request and response models
- [ ] Multi-stage Dockerfile, non-root
- [ ] Deploy to Hugging Face Spaces
- [ ] KServe manifests, validated against a local kind cluster

---

## Phase 6: Dashboard

Ships: a public dashboard.

Entry: Phase 5 serving estimates.
Done when: a visitor can look up a player, see the interval, and read what the
metric cannot tell them without having to go looking for it.
Limit: review-bound. Design judgement does not delegate well.

- [ ] Player lookup with credible intervals
- [ ] Player comparison
- [ ] Measured reliability of each input, shown honestly
- [ ] A page saying what the metric cannot tell you

---

## Phase 7: Automation

Entry: Phase 5 complete.
Done when: a scheduled run refreshes data, retrains, and publishes without
anyone touching it, and a drift report appears in the docs.
Limit: agent-parallel.

- [ ] Scheduled refresh, retrain, publish
- [ ] Evidently drift report rendered into the docs
- [ ] Model card

---

## Phase 8: Launch

Entry: Phases 3 and 4 complete. The dashboard is optional for this.
Done when: the method is written up including its limitations, and it has been
put in front of people who will argue with it.
Limit: judgement and writing. Does not delegate.

- [ ] Method write-up, including limitations
- [ ] Post to r/nbaanalytics and the APBRmetrics forum
- [ ] Consider a Journal of Open Source Software submission

---

## Deliberately out of scope

- Betting tools of any kind
- Redistributing paywalled metrics
- Kubernetes in production
- Automated feature engineering
