# Roadmap

Twelve weeks to first public release. Five shipping events. Tracked as issues once
the repository is public; this file is the outline.

## Week 0: Foundation

Ships: public repository

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

## Weeks 1-2: Data layer

Ships: dataset v0

- [ ] hoopR bulk Parquet downloader, 2002 to present
- [ ] NBA stats client with rate limiting and backoff
- [ ] pandera schemas for every table
- [ ] Validation: completeness, consistency, accuracy, temporal integrity
- [ ] Nightly refresh workflow
- [ ] Measure the possession coefficient per season instead of hard-coding 0.44
- [x] Save the browser-only citations by hand (16 archived)
- [x] Record every broken citation in `docs/methodology/errata.md`

  The original wording said "replace or remove" the broken citations. That is not
  possible: `docs/research/` is a protected record and is never edited. The errata
  page is the resolution, and it names each dead source and what it used to support.

## Weeks 3-4: RAPM

Ships: validation report

- [ ] Possession and stint extraction via pbpstats
- [ ] Sparse design matrix builder
- [ ] Ridge solver, cross-validated lambda, multi-season windows
- [ ] Bootstrap standard errors
- [ ] Property tests: possessions reconcile, five a side, order invariance
- [ ] **Decision gate:** Spearman above 0.85 against published RAPM

## Weeks 5-7: The measurement model

- [ ] Split-half reliability with Spearman-Brown correction
- [ ] NumPyro hierarchical fusion model
- [ ] LightGBM and ridge baselines, tuned with Optuna, tracked in MLflow
- [ ] SHAP attributions
- [ ] Interval calibration check
- [ ] **Run the claim under test and publish the answer either way**

## Week 8: Package

Ships: v0.1.0 on PyPI

- [ ] Freeze the public API, complete docstrings
- [ ] Configure Trusted Publishing on PyPI
- [ ] Zenodo integration for a citable DOI

## Week 9: API

Ships: live endpoint

- [ ] FastAPI service with request and response models
- [ ] Multi-stage Dockerfile, non-root
- [ ] Deploy to Hugging Face Spaces
- [ ] KServe manifests, validated against a local kind cluster

## Week 10: Dashboard

Ships: public dashboard

- [ ] Player lookup with credible intervals
- [ ] Player comparison
- [ ] Measured reliability of each input, shown honestly
- [ ] A page saying what the metric cannot tell you

## Week 11: Automation

- [ ] Scheduled refresh, retrain, publish
- [ ] Evidently drift report rendered into the docs
- [ ] Model card

## Week 12: Launch

- [ ] Method write-up, including limitations
- [ ] Post to r/nbaanalytics and the APBRmetrics forum
- [ ] Consider a Journal of Open Source Software submission

## Deliberately out of scope

- Betting tools of any kind
- Redistributing paywalled metrics
- Kubernetes in production
- Automated feature engineering
