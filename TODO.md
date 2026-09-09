# Roadmap

Twelve weeks to first public release. Five shipping events. Tracked as issues once
the repository is public; this file is the outline.

## Week 0 — Foundation → **ship: public repository**

- [x] `git init`, Apache-2.0 licence, `.gitignore` that blocks data
- [x] `pyproject.toml` with uv, ruff, mypy strict, pytest
- [x] Pre-commit hooks, including a hook that blocks committing data
- [x] CI: lint, types, tests on Python 3.10 to 3.13, build, docs
- [x] Release workflow using PyPI Trusted Publishing
- [x] Governance: contributing, code of conduct, security policy, templates
- [x] Docs site scaffold, building in strict mode
- [x] `nba_impact.paths` and the CLI skeleton
- [x] Bibliography archiver
- [ ] Push to GitHub, enable Pages, enable private vulnerability reporting

## Weeks 1-2 — Data layer → **ship: dataset v0**

- [ ] hoopR bulk Parquet downloader, 2002 to present
- [ ] NBA stats client with rate limiting and backoff
- [ ] pandera schemas for every table
- [ ] Validation: completeness, consistency, accuracy, temporal integrity
- [ ] Nightly refresh workflow
- [ ] Manually save the 25 browser-only citations
- [ ] Replace or remove the broken citations, starting with the EPM one

## Weeks 3-4 — RAPM → **ship: validation report**

- [ ] Possession and stint extraction via pbpstats
- [ ] Sparse design matrix builder
- [ ] Ridge solver, cross-validated lambda, multi-season windows
- [ ] Bootstrap standard errors
- [ ] Property tests: possessions reconcile, five a side, order invariance
- [ ] **Decision gate:** Spearman above 0.85 against published RAPM

## Weeks 5-7 — The measurement model

- [ ] Split-half reliability with Spearman-Brown correction
- [ ] NumPyro hierarchical fusion model
- [ ] LightGBM and ridge baselines, tuned with Optuna, tracked in MLflow
- [ ] SHAP attributions
- [ ] Interval calibration check
- [ ] **Run the claim under test and publish the answer either way**

## Week 8 — Package → **ship: v0.1.0 on PyPI**

- [ ] Freeze the public API, complete docstrings
- [ ] Configure Trusted Publishing on PyPI
- [ ] Zenodo integration for a citable DOI

## Week 9 — API → **ship: live endpoint**

- [ ] FastAPI service with request and response models
- [ ] Multi-stage Dockerfile, non-root
- [ ] Deploy to Hugging Face Spaces
- [ ] KServe manifests, validated against a local kind cluster

## Week 10 — Dashboard → **ship: public dashboard**

- [ ] Player lookup with credible intervals
- [ ] Player comparison
- [ ] Measured reliability of each input, shown honestly
- [ ] A page saying what the metric cannot tell you

## Week 11 — Automation

- [ ] Scheduled refresh, retrain, publish
- [ ] Evidently drift report rendered into the docs
- [ ] Model card

## Week 12 — Launch

- [ ] Method write-up, including limitations
- [ ] Post to r/nbaanalytics and the APBRmetrics forum
- [ ] Consider a Journal of Open Source Software submission

## Deliberately out of scope

- Betting tools of any kind
- Redistributing paywalled metrics
- Kubernetes in production
- Automated feature engineering
