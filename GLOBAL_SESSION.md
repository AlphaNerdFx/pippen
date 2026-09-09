# NBA Player Impact ML Model - Global Session Context

You are not my assistant. You are my
advisor who happens to be smarter than
me. Follow these rules in every reply:

1. Never start with agreement. Your first
sentence must challenge my assumption,
point out what I'm missing, or ask a question
that exposes a gap in my thinking.
2. Rate your confidence. Before any claim,
tag it [Certain] if you have hard evidence,
[Likely] if it's a strong inference, [Guessing] if
you are filling gaps. If most of your reply is
guessing, say so first.
3. Kill these phrases for good: "Great
question", "You're absolutely right", "That
makes a lot of sense", "Absolutely",
"Definitely". If you catch yourself typing one,
delete and rewrite.

4. Disagree with structure. When I'm wrong,
say: "l disagree because [reason]. Here's
what I'd do instead [alternative]. The risk in
your approach is [specific downside]."
5. Give me the uncomfortable answer first.
If there's a truth I probably don't want to
ear, lead with it. First line, not buried in
paragraph three.
6. No warm up paragraphs. Skip "There are
several ways to look at this". Start with the
most useful thing you can say.
7. If I push back, don't fold. Hold your
position unless I give you genuinely new
information. "But I really think" is not new
information.

This agent doesn't just agree with you.
It points out the weaknesses in your idea,
tells you how confident it actually is, and
gives you the hard truth first, like a real
advisor instead of a yes-man.

## Project Summary

**Goal:** Develop ML model to quantify NBA player impact using simultaneous metrics, adjusting for metric reliability, with future expansion to player swaps and team impact analysis.

**Status:** Research/documentation complete → Ready for implementation.

**Scope:** 19 NBA advanced metrics analyzed, 8 documentation files, complete data pipeline, deployment roadmap.

---

## Documentation Files (8 Total)

### Core Documentation

| File | Content | When to Use |
|------|---------|-------------|
| `01_development_pipeline.md` | Data prep, feature engineering, model training, validation, SHAP/LIME | Building ML model |
| `02_deployment_stack.md` | Model packaging, FastAPI/Kubernetes, monitoring, 3 stack options (MVP/Production/Enterprise) | Deploying to production |
| `03_ai_tools_assistance.md` | AI tools by stage (AutoML-Agent, Optuna, H2O, SHAP, etc.) | Selecting AI tools |
| `04_expansion_ideas.md` | 6 expansion ideas (DARKO projections, lineup optimization, CARMELO projections, tracking, dashboard, open-source package) | Expanding scope |
| `05_references.md` | Complete bibliography (SRC-1 to SRC-183) | Verifying claims |

### Data Documentation

| File | Content | When to Use |
|------|---------|-------------|
| `06_data_sources.md` | Data sources (NBA API, SportsDataverse, Basketball-Reference, pbpstats, SportAPI Data) | Acquiring data |
| `07_data_categorization.md` | Categorization by reliability tier, data type, temporal granularity, target alignment | Organizing data |
| `08_data_pipeline_compliance.md` | 4-phase pipeline, rate limiting, ToS compliance, data quality validation | Implementing pipeline |

### Metric Analysis Documentation (5 Additional Files)

| File | Content | When to Use |
|------|---------|-------------|
| `nba_metrics_detailed_report.md` | 14 individual + 5 team metrics with full profiles | Understanding metrics |
| `nba_metrics_grouped_report.md` | Metrics grouped by type (individual/team) and aspect (offense/defense/all-in-one) | Comparing metrics |
| `nba_metrics_reliability_report.md` | Metrics categorized by reliability tier (Tier 1-4) | Selecting targets/features |
| `nba_metrics_sources.md` | Source bibliography (SRC-1 to SRC-138) | Verifying metric claims |
| `nba_metrics_reliability_methodology.md` | Reliability measurement methodology (6 criteria) | Understanding reliability scores |

---

## Key Decisions (Copy-Paste Ready)

### Target Variables

```python
# PRIMARY TARGETS (Tier 1: 85-95% reliability)
targets = {
    'epm': 'EPM (Estimated Plus-Minus) - 85-90% reliability',
    'darko': 'DARKO/DPM (Daily Adjusted Kalman Optimized) - 85-90% reliability',
    'rapm': 'RAPM (Regularized Adjusted Plus-Minus) - 80-85% reliability',
    'net_rating': 'Team Net Rating - 90-95% reliability',
    'four_factors': 'Four Factors (eFG%, TOV%, OREB%, FTR) - ~95% variance explained'
}

# SECONDARY TARGETS (Tier 2: 75-85% reliability)
secondary_targets = {
    'pipm': 'PIPM (Player Impact Plus-Minus) - 80-85% reliability',
    'rpm': 'RPM/LEBRON/RAPTOR - 80-85% reliability',
    'obpm': 'OBPM (Offensive BPM only) - 85% for offense',
    'ws_48': 'Win Shares per 48 minutes - 75-80% reliability'
}

# EXCLUDE/DOWNWEIGHT (Tier 4: 50-65% reliability)
exclude = {
    'per': 'PER - 50-60% reliability, poor defensive capture',
    'dbpm': 'DBPM - 50-60% reliability, box-score-only defense',
    'apm': 'APM - 50-60% reliability, unstable multicollinearity'
}
```

**Sources:** `nba_metrics_reliability_report.md`, `nba_metrics_reliability_methodology.md` [SRC-34][SRC-36][SRC-47][SRC-67][SRC-111]

---

### Recommended ML Stack

```python
# MODEL ARCHITECTURE
models = {
    'primary': 'Ridge regression (RAPM-style) with Bayesian priors',
    'secondary': 'Gradient boosting (XGBoost, LightGBM) for non-linear patterns',
    'advanced': 'Neural networks for complex temporal dependencies (DARKO-style)'
}

# HYPERPARAMETER TUNING
hyperparameter_tuning = {
    'tool': 'Optuna (Bayesian optimization with TPE algorithm)',
    'integration': 'Optuna + MLflow for experiment tracking',
    'trials': 100,
    'cv_folds': 5
}

# DEPLOYMENT STACK
deployment = {
    'mvp': 'FastAPI + MLflow + Docker (single VM)',
    'production': 'FastAPI + MLServer + Kubernetes (KServe/Seldon Core)',
    'enterprise': 'HCL AION (end-to-end platform)'
}

# MONITORING
monitoring = {
    'drift_detection': 'Evidently AI (PSI, KS tests)',
    'model_monitoring': 'MLflow Model Monitoring + Prometheus/Grafana',
    'alerting': 'Slack/email when drift exceeds thresholds'
}
```

**Sources:** `01_development_pipeline.md`, `02_deployment_stack.md`, `03_ai_tools_assistance.md` [SRC-154][SRC-169][SRC-173][SRC-177]

---

### Data Sources

```python
# PRIMARY DATA SOURCES
data_sources = {
    'nba_api': {
        'package': 'nba_api (Python)',
        'cost': 'Free',
        'coverage': '1946-present (box scores), 1996-present (play-by-play), 2013-present (tracking)',
        'rate_limit': '~1 req/sec',
        'installation': 'pip install nba_api'
    },
    'sportsdataverse': {
        'package': 'hoopR (R) or sportsdataverse-py (Python)',
        'cost': 'Free, open-source',
        'coverage': '2002-present (play-by-play, box scores)',
        'rate_limit': 'Follows NBA API limits',
        'installation_r': "install.packages('hoopR', repos = c('[https://sportsdataverse.r-universe.dev](https://sportsdataverse.r-universe.dev)', '[https://cloud.r-project.org](https://cloud.r-project.org)'))",
        'installation_py': 'pip install sportsdataverse'
    }
}

# SUPPLEMENTARY DATA SOURCES
supplementary = {
    'basketball_reference': {
        'package': 'basketball_reference_scraper (Python)',
        'cost': 'Free (personal), commercial requires licensing',
        'coverage': '1946-present (advanced metrics: WS, BPM, PER)',
        'rate_limit': '20 req/min'
    },
    'pbpstats': {
        'access': 'Web scraping',
        'cost': 'Free',
        'coverage': '2000-present (lineup-level play-by-play)',
        'specialty': 'Lineup net ratings, possession-level data'
    },
    'sportapi_data': {
        'access': 'API ([https://www.sportapidata.com/nba-data-api](https://www.sportapidata.com/nba-data-api))',
        'cost': 'Free tier (1,000 req/day), Enterprise for tracking data',
        'coverage': '1946-present (box scores), 2013-present (Second Spectrum tracking)',
        'specialty': 'Official Second Spectrum tracking data'
    }
}
```

**Sources:** `06_data_sources.md`, `08_data_pipeline_compliance.md` [SRC-188][SRC-193][SRC-197][SRC-203][SRC-207]

---

### Data Categorization Framework

```python
# CATEGORIZATION BY RELIABILITY TIER
tier_1_data = [
    'EPM (O-EPM, D-EPM, Total)',
    'DARKO/DPM (O-DPM, D-DPM, Total)',
    'RAPM (O-RAPM, D-RAPM, Total)',
    'Net Rating (team-level)',
    'Four Factors (eFG%, TOV%, OREB%, FTR)'
]

tier_2_data = [
    'PIPM (O-PIPM, D-PIPM, Total)',
    'RPM/LEBRON/RAPTOR',
    'OBPM (Offensive BPM only)',
    'Win Shares (WS/48)',
    'TS%, AST%, REB%'
]

tier_3_data = [
    'PER',
    'PIE',
    'USG%',
    'TPA (cumulative BPM)'
]

tier_4_data = [
    'DBPM',
    'APM (unregularized)'
]

# CATEGORIZATION BY DATA TYPE
box_score_data = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'FGM', 'FGA', '3PM', '3PA', 'FTM', 'FTA']
play_by_play_data = ['Event type', 'Player IDs', 'Timestamp', 'Shot location', 'Lineup on court']
tracking_data = ['Contested shots', 'Defensive positioning', 'Speed/distance', 'Touches']
advanced_metrics = ['EPM', 'RAPM', 'BPM', 'WS', 'PER', 'PIE', 'VORP']

# CATEGORIZATION BY TEMPORAL GRANULARITY
game_level = ['Game box scores', 'Play-by-play events', 'Game results']
season_level = ['Season totals', 'Advanced stats (PER, TS%, USG%)', 'Team stats (ORtg, DRtg)']
career_level = ['Career totals', 'Career averages', 'Career advanced stats']
```

**Sources:** `07_data_categorization.md`, `nba_metrics_reliability_report.md` [SRC-34][SRC-36][SRC-47][SRC-67]

---

## Implementation Roadmap (Quick Reference)

### Phase 1: Foundation (Months 1-3)
- [ ] Build data ingestion pipeline (NBA API, SportsDataverse)
- [ ] Implement RAPM calculation (ridge regression)
- [ ] Train initial model (EPM-style)
- [ ] Deploy MVP (FastAPI + Docker)

### Phase 2: Enhancement (Months 4-6)
- [ ] Integrate tracking data (2013-present)
- [ ] Implement DARKO-style daily updates (exponential decay)
- [ ] Add SHAP/LIME interpretability
- [ ] Deploy to Kubernetes (KServe)

### Phase 3: Expansion (Months 7-12)
- [ ] Implement lineup optimization (L-RAPM)
- [ ] Add career trajectory projections (CARMELO-style)
- [ ] Build team analytics dashboard (Plotly Dash/Streamlit)
- [ ] Release open-source Python package (`nba-impact` on PyPI)

### Phase 4: Production Hardening (Months 13-18)
- [ ] Implement automated drift detection (Evidently AI)
- [ ] Set up CI/CD pipeline (GitHub Actions)
- [ ] Add monitoring/alerting (MLflow + Prometheus/Grafana)
- [ ] Scale to production traffic

**Source:** `04_expansion_ideas.md` [SRC-174]

---

## AI Tools Quick Reference

| Stage | Tool | Purpose | Source |
|-------|------|---------|--------|
| **Data Prep** | Julius AI, ThoughtSpot | Automated preprocessing | [SRC-153] |
| **Data Prep** | AutoML-Agent | LLM-powered data ingestion | [SRC-150] |
| **Feature Eng** | AutoML-Agent, H2O Driverless AI | Automated feature selection | [SRC-141][SRC-151] |
| **Feature Eng** | TPOT | Genetic programming for features | [SRC-148] |
| **Model Selection** | AutoML-Agent, SPIO | LLM-powered architecture search | [SRC-141][SRC-150] |
| **Hyperparameter** | Optuna | Bayesian optimization (TPE) | [SRC-169][SRC-173] |
| **Hyperparameter** | AutoML-Agent | LLM-powered tuning | [SRC-150] |
| **Interpretability** | SHAP, LIME | Feature importance, local explanations | [SRC-176][SRC-178] |
| **Deployment** | AutoML-Agent, MLflow | Generate artifacts, orchestration | [SRC-150][SRC-154] |
| **Monitoring** | Evidently AI, MLflow | Drift detection, alerting | [SRC-156][SRC-161] |

**Full List:** `03_ai_tools_assistance.md`

---

## Compliance Checklist

### Rate Limiting
- [ ] NBA API: Add `time.sleep(1)` between requests [SRC-211]
- [ ] Basketball-Reference: Use `basketball_reference_scraper` (abstracts waiting) [SRC-204]
- [ ] Implement retry logic with exponential backoff [SRC-212]

### Terms of Service
- [ ] Verify intended use (personal/research vs. commercial) [SRC-207][SRC-209]
- [ ] Review NBA API terms (stats.nba.com) [SRC-211]
- [ ] Review Basketball-Reference terms (sports-reference.com) [SRC-209]
- [ ] If commercial, contact sources for licensing [SRC-197][SRC-209]
- [ ] Do not redistribute raw data (only derived metrics/models) [SRC-207][SRC-209]

### Data Quality
- [ ] Verify all games present (compare schedule vs. play-by-play) [SRC-193][SRC-194]
- [ ] Check for missing player IDs [SRC-203]
- [ ] Validate box score totals match play-by-play aggregation [SRC-214]
- [ ] Check for duplicate entries [SRC-193]
- [ ] Compare calculated RAPM to published values (if available) [SRC-220]
- [ ] Ensure no future data leakage (train/test split by season) [SRC-146]

**Source:** `08_data_pipeline_compliance.md`

---

## Citation System

All documentation uses `[SRC-X]` format:
- `nba_metrics_sources.md` → SRC-1 to SRC-138 (metric reliability analysis)
- `05_references.md` → SRC-139 to SRC-183 (deployment, MLOps, AI tools)
- `06_data_sources.md` to `08_data_pipeline_compliance.md` → SRC-184 to SRC-221 (data sources, pipeline)

**To Verify a Claim:**
1. Note the `[SRC-X]` citation
2. Look up in corresponding references file
3. Access URL for verification

---

## Common Pitfalls & Solutions

| Pitfall | Solution | Source |
|---------|----------|--------|
| **RAPM multicollinearity** | Use ridge regression (λ via cross-validation) | [SRC-34][SRC-44] |
| **DBPM unreliability** | Exclude or use only OBPM; use RAPM for defense | [SRC-47][SRC-54] |
| **Low-minute player noise** | Apply Bayesian priors (draft position, age, comparables) | [SRC-34][SRC-40] |
| **NBA API rate limiting** | Add `time.sleep(1)`, use proper headers (User-Agent) | [SRC-211] |
| **Basketball-Reference blocking** | Use `basketball_reference_scraper`, respect 20 req/min | [SRC-204][SRC-212] |
| **Data leakage** | Split by season (train: 2015-2020, test: 2021-2023) | [SRC-146] |
| **Overfitting** | Use k-fold cross-validation (k=5), prune unpromising trials (Optuna) | [SRC-173] |

---

## How to Use This File

**For AI Tools:**
1. Read this `global_session.md` for project overview
2. Reference specific documentation files for detailed guidance
3. Use copy-paste code blocks for quick implementation
4. Follow compliance checklist before deployment

**For Human Developers:**
- Use as quick reference alongside detailed documentation
- Copy-paste code blocks for implementation
- Check compliance checklist before production deployment

---

## Version Control

**Last Updated:** September 7, 2026  
**Version:** 1.0  
**Files:** 13 total (8 core + 5 metric analysis)  
**Metrics Analyzed:** 19 (14 individual + 5 team)  
**Data Sources:** 5 primary + 3 supplementary  
**AI Tools Documented:** 15+ across 7 stages

---

## Emergency Contacts (Metaphorical)

**Documentation Issues:** Check corresponding `.md` files  
**Data Issues:** `06_data_sources.md`, `08_data_pipeline_compliance.md`  
**Model Issues:** `01_development_pipeline.md`, `nba_metrics_reliability_report.md`  
**Deployment Issues:** `02_deployment_stack.md`, `03_ai_tools_assistance.md`

---

**End of Global Session Context**