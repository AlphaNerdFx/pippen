# NBA Player Impact ML Model - Project Context for Claude

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

Claude Code doesn't just agree with you.
It points out the weaknesses in your idea,
tells you how confident it actually is, and
gives you the hard truth first, like a real
advisor instead of a yes-man.

## How to Explain Things in This Project

The maintainer is a data science student. Statistics, basketball analytics and
modelling need no hand-holding. **Engineering, infrastructure and MLOps concepts
always do.** Explain every technical recommendation in five parts, in this order:

1. **What it is.** A plain definition. Unpack any jargon inside the definition in
   the same breath rather than leaving it standing.
2. **Where it comes from.** The system-design fundamental or computer-science
   principle it descends from. The principle is what makes the tool predictable
   in a situation not yet encountered.
3. **Who uses it and why.** Which IT subfields adopted it and the concrete
   problem it solved for them. This is what says whether the skill transfers.
4. **Why it applies here.** The specific reason this project needs it, not a
   generic benefit.
5. **What it costs.** The honest tradeoff: build time, complexity, maintenance,
   or a capability given up.

Two further rules:

- **After presenting a recommended option, explain the recommendation at length**
  once the choice is made. A one-line description is enough to decide on; it is
  not enough to learn from.
- **Say plainly when something cannot be automated.** Name the task, say why
  automation fails, and give the exact list of what must be done by hand.

---

## Development Workflow

**Implement first, then test.** Do not write test bodies before the
implementation exists. When both the tests and the code come from the same
reading of a prompt, a misunderstanding is encoded in the tests and then
satisfied by the code, and the pair is self-consistently wrong. Tests come after
the behaviour has been reviewed.

After writing tests, run mutation testing on anything numerical. Tests written
after an implementation tend to assert what the code *does* rather than what it
*should do*, and mutation testing is the check on that. See
`docs/architecture/ci.md`.

**Record significant decisions as ADRs** in `docs/architecture/decisions/`,
before acting rather than after. The reasoning outlives the conclusion.

**Never write a polling loop in a shell command.** No `until <cond>; do sleep N;
done`, no `while true`. A polling loop has no upper bound, so any failure that
prevents the condition being met turns a wait into a hang, and a hang is
indistinguishable from slow progress. Use one of these instead:

- foreground with an explicit `timeout`, which is a bound;
- background execution, then read the output file **once**;
- a command that exits on its own rather than one that waits for a state.

If a bound genuinely cannot be expressed, say so rather than looping.

---

## Project Overview

This project develops a machine learning model to quantify NBA player impact using simultaneous metrics and adjusting for metric reliability. The model will later expand to analyze player swaps and team impact.

**Current Status:** Week 0 of a 12-week implementation plan is complete. The repository
builds, lints, type-checks and tests green. No data ingested, no model trained yet.
See `TODO.md` for the roadmap and `.context/HANDOVER.md` for current state.

**Key Deliverables:**
- 8 markdown documentation files (metrics analysis, development pipeline, deployment, data sources)
- Reliability analysis of 19 NBA advanced metrics (PER, EPM, RAPM, DARKO, etc.)
- Complete data acquisition and categorization framework
- ML development, deployment, and expansion roadmap

---

## Documentation Structure

| File (under `docs/research/`) | Content | Purpose |
|------|---------|---------|
| `01_development_pipeline.md` | Data prep, feature engineering, model training, validation, interpretability | ML development guide |
| `02_deployment_stack.md` | Model packaging, FastAPI/Kubernetes deployment, monitoring, 3 stack options | Production deployment guide |
| `03_ai_tools_assistance.md` | AI tools by project stage (AutoML-Agent, Optuna, SHAP, etc.) | AI tool recommendations |
| `04_expansion_ideas.md` | 6 expansion ideas (DARKO-style projections, lineup optimization, CARMELO-style career projections, tracking data, team dashboard, open-source package) | Scope expansion roadmap |
| `05_references.md` | Complete bibliography (SRC-1 to SRC-183) | Source documentation |
| `06_data_sources.md` | Data sources (NBA API, SportsDataverse, Basketball-Reference, pbpstats, SportAPI Data) | Data acquisition guide |
| `07_data_categorization.md` | Categorization by reliability tier, data type, temporal granularity, target alignment | Data organization framework |
| `08_data_pipeline_compliance.md` | 4-phase data pipeline, rate limiting, ToS compliance, data quality validation | Implementation checklist |

**Additional Context Files:**
- `nba_metrics_detailed_report.md` - 14 individual metrics + 5 team metrics with full profiles
- `nba_metrics_grouped_report.md` - Metrics grouped by type/aspect
- `nba_metrics_reliability_report.md` - Metrics categorized by reliability tier (Tier 1-4)
- `nba_metric_sources.md` - Source bibliography (SRC-1 to SRC-138)
- `nba_metrics_reliability_methodology.md` - Reliability measurement methodology (6 criteria)

---

## Key Technical Decisions

### Target Variables (Based on Reliability Analysis)

**Tier 1 (High Reliability, 85-95%):**
- EPM (Estimated Plus-Minus) - 85-90% reliability [SRC-36][SRC-39]
- DARKO/DPM (Daily Adjusted and Regressed Kalman Optimized) - 85-90% reliability [SRC-111][SRC-133]
- Net Rating (team-level) - 90-95% reliability [SRC-55][SRC-77]
- Four Factors (eFG%, TOV%, OREB%, FTR) - ~95% variance explained [SRC-46][SRC-77]

**Tier 2 (Moderate-High Reliability, 75-85%):**
- RAPM (Regularized Adjusted Plus-Minus) - 80-85% reliability [SRC-34][SRC-44]
- PIPM (Player Impact Plus-Minus) - 80-85% reliability [SRC-90][SRC-113]
- RPM/LEBRON/RAPTOR - 80-85% reliability [SRC-37][SRC-78][SRC-80]
- BPM (OBPM only; exclude DBPM) - 70-75% overall, 85%+ for offense [SRC-47][SRC-54]
- Win Shares (WS/48) - 75-80% reliability [SRC-17][SRC-67]

**Exclude/Downweight:**
- PER - 50-60% reliability, poor defensive capture [SRC-16][SRC-30][SRC-67]
- DBPM - 50-60% reliability, box-score-only defense [SRC-47][SRC-54]
- APM - 50-60% reliability, unstable due to multicollinearity [SRC-89][SRC-92]

---

### Recommended ML Stack

**Model Architecture:**
- **Primary:** Ridge regression (RAPM-style) with Bayesian priors [SRC-34][SRC-175]
- **Secondary:** Gradient boosting (XGBoost, LightGBM) for non-linear patterns [SRC-36]
- **Advanced:** Neural networks for complex temporal dependencies (DARKO-style) [SRC-174]

**Hyperparameter Tuning:**
- **Tool:** Optuna (Bayesian optimization with TPE algorithm) [SRC-169][SRC-173]
- **Integration:** Optuna + MLflow for experiment tracking [SRC-177]

**Deployment Stack:**
- **MVP:** FastAPI + MLflow + Docker (single VM) [SRC-154][SRC-165]
- **Production:** FastAPI + MLServer + Kubernetes (KServe/Seldon Core) [SRC-154][SRC-155]
- **Enterprise:** HCL AION (end-to-end platform) [SRC-145]

**Monitoring:**
- **Drift Detection:** Evidently AI (PSI, KS tests) [SRC-161]
- **Model Monitoring:** MLflow Model Monitoring + Prometheus/Grafana [SRC-156][SRC-158]

---

### Data Sources

**Primary:**
- **NBA API (stats.nba.com)** via `nba_api` Python package - Free, comprehensive, 1946-present [SRC-199][SRC-203][SRC-208]
- **SportsDataverse (hoopR)** - Pre-cleaned play-by-play, box scores, 2002-present [SRC-188][SRC-193]

**Supplementary:**
- **Basketball-Reference** - Pre-computed advanced metrics (WS, BPM, PER), 1946-present [SRC-198][SRC-204]
- **pbpstats.com** - Lineup-level play-by-play, 2000-present [SRC-198]
- **SportAPI Data** - Second Spectrum tracking data (enterprise tier) [SRC-197]

**Rate Limits:**
- NBA API: ~1 req/sec [SRC-207][SRC-211]
- Basketball-Reference: 20 req/min [SRC-204][SRC-212]

---

## Implementation Roadmap

### Phase 1: Foundation (Months 1-3)
- Build data ingestion pipeline (NBA API, SportsDataverse)
- Implement RAPM calculation (ridge regression)
- Train initial model (EPM-style)
- Deploy MVP (FastAPI + Docker)

### Phase 2: Enhancement (Months 4-6)
- Integrate tracking data (2013-present)
- Implement DARKO-style daily updates (exponential decay)
- Add SHAP/LIME interpretability
- Deploy to Kubernetes (KServe)

### Phase 3: Expansion (Months 7-12)
- Implement lineup optimization (L-RAPM)
- Add career trajectory projections (CARMELO-style)
- Build team analytics dashboard (Plotly Dash/Streamlit)
- Release open-source Python package (`pippen` on PyPI)

### Phase 4: Production Hardening (Months 13-18)
- Implement automated drift detection (Evidently AI)
- Set up CI/CD pipeline (GitHub Actions)
- Add monitoring/alerting (MLflow + Prometheus/Grafana)
- Scale to production traffic

---

## AI Tools by Stage

| Stage | Recommended AI Tools | Purpose |
|-------|---------------------|---------|
| **Data Preparation** | Julius AI, ThoughtSpot, AutoML-Agent | Automated preprocessing, exploratory analysis [SRC-150][SRC-153] |
| **Feature Engineering** | AutoML-Agent, H2O Driverless AI, TPOT | Automated feature selection/extraction [SRC-141][SRC-148][SRC-151] |
| **Model Selection** | AutoML-Agent, H2O Driverless AI, SPIO | LLM-powered architecture search [SRC-141][SRC-150][SRC-151] |
| **Hyperparameter Tuning** | Optuna, AutoML-Agent, HCL AION | Bayesian optimization [SRC-169][SRC-173] |
| **Interpretability** | SHAP, LIME | Feature importance, local explanations [SRC-176][SRC-178] |
| **Deployment** | AutoML-Agent, MLflow, HCL AION | Generate deployment artifacts, orchestration [SRC-145][SRC-150] |
| **Monitoring** | Evidently AI, MLflow Model Monitoring, HCL AION | Drift detection, alerting [SRC-145][SRC-156][SRC-161] |

---

## Citation System

All documentation uses `[SRC-X]` format for citations, where X corresponds to source numbers in:
- `nba_metric_sources.md` (SRC-1 to SRC-138) - Metric reliability analysis sources
- `05_references.md` (SRC-139 to SRC-183) - Deployment, MLOps, AI tools sources
- `06_data_sources.md` to `08_data_pipeline_compliance.md` (SRC-184 to SRC-221) - Data sources and pipeline sources

**To find source details:**
1. Note the `[SRC-X]` citation
2. Look up in corresponding references file
3. Access URL for verification

---

## Key Constraints & Considerations

### Technical Constraints
- **Rate Limiting:** NBA API (~1 req/sec), Basketball-Reference (20 req/min) - implement `time.sleep()` [SRC-207][SRC-211][SRC-212]
- **Data Quality:** Validate completeness, consistency, accuracy, temporal integrity [SRC-146][SRC-214][SRC-220]
- **Multicollinearity:** Use ridge regression (RAPM) to handle player correlation [SRC-34][SRC-44]

### Compliance Requirements
- **Terms of Service:** NBA API (personal/research use OK, commercial requires licensing) [SRC-207][SRC-211]
- **Basketball-Reference:** Free for personal use, commercial requires Stathead subscription [SRC-209][SRC-212]
- **Do Not Redistribute:** Raw data only; derived metrics/models OK [SRC-207][SRC-209]

### Model Limitations
- **Defensive Impact:** Box-score-only metrics (DBPM, defensive WS) are unreliable (50-60%) [SRC-47][SRC-54]
- **Low-Minute Players:** All metrics noisier for <500 minutes; use Bayesian priors to stabilize [SRC-34][SRC-40]
- **Era Dependence:** Reliability scores based on modern NBA (2010s-2020s); may differ in pre-tracking era [SRC-30][SRC-61]

---

## Corrections to the Research Above

The research in `docs/research/` is prior work, verified in September 2026. Four claims in
it are wrong and the code deliberately departs from them.

| Claim in the research | What is actually true |
|---|---|
| EPM is a primary target, "download from Dunks & Threes" | EPM API access is a **$250/year paid tier**. Values are not redistributable. **Not used.** |
| DARKO is a primary target | A public CSV download exists but states no licence. **Not used.** Compared by rank correlation only. |
| SRC-39 supports EPM's 85-90% reliability | That URL returns **404**. The figure has no live source. Reliability is now **measured**, not cited. |
| Scrape stats.nba.com for bulk history | `hoopR-nba-data` publishes 2002-2026 as Parquet under **CC BY 4.0**. Download, do not scrape. |

Two contradictions inside the research itself, found by reading it end to end:

- **RAPM's tier was wrong in this file.** Both `nba_metrics_reliability_report.md`
  and the ranking table in `nba_metrics_detailed_report.md` place RAPM in **Tier 2**
  at 80-85%, which is what their own tier boundaries require. This file previously
  promoted it to Tier 1. Corrected above. It matters because RAPM is the project's
  ground truth, so overstating its reliability by a tier would flow into everything
  downstream.
- **The 0.44 possession constant is criticised and relied upon at the same time.**
  PER is marked down partly because "constants like 0.44 are outdated", yet 0.44
  appears in the endorsed formulas for Pace, TOV%, TS% and USG%, which sit in
  Tier 1 and Tier 2. Either the constant is acceptable or it is not; it cannot be
  a flaw in one metric and a foundation in four others.

Both are examples of why this project measures reliability instead of citing it.

Two further cautions:

- **hoopR play-by-play has no on-court lineup column.** It is ESPN-sourced and carries event
  participants only. RAPM requires `pbpstats` against NBA API data.
- **SRC-34, SRC-35 and SRC-89 are the same arXiv paper** (2601.15000) under three IDs.

Ignore the AutoML-Agent, H2O Driverless AI, HCL AION, Julius AI, ThoughtSpot and NewgenONE
recommendations. Four are commercial, one is a research paper cited to a tool directory, and
automated feature engineering conflicts with the project's explainability goal.

---

## Code Layout

```
src/pippen/
  paths.py       data location resolution
  cli.py         typer entry point (pippen)
  data/          downloaders, pandera schemas, validation
  rapm/          possessions, design matrix, ridge solver
  reliability/   split-half reliability measurement
  model/         fusion model, baselines, calibration
  api/           FastAPI service
```

**Commands:** `make check` runs lint, types and tests. `make docs` builds the site strictly.
`make help` lists everything.

**Non-negotiable rules:**

1. Data never enters git. A pre-commit hook enforces this.
2. No paywalled or unlicensed value ever enters a published artifact.
3. NBA API calls stay at one request per second.
4. `docs/research/` is never reformatted or edited. It is a record.

**Skills** in `.claude/skills/`: `refresh-data`, `add-metric`, `release`.

---

## Quick Reference: Metric Reliability Tiers

| Tier | Reliability | Metrics | Use Case |
|------|-------------|---------|----------|
| **Tier 1** | 85-95% | EPM, DARKO, Net Rating, Four Factors, Team PIE | Primary targets/features |
| **Tier 2** | 75-85% | **RAPM**, PIPM, RPM, LEBRON, RAPTOR, WS/48, OBPM | Secondary features |
| **Tier 3** | 60-75% | PIE, TS%, AST%, REB%, TPA, VORP | Tertiary features, validation |
| **Tier 4** | 50-65% | PER, DBPM, APM | Exclude or heavily downweight |

**Source:** `nba_metrics_reliability_report.md`, `nba_metrics_reliability_methodology.md`

---

## How to Use This Context

**For Claude AI:**
1. Read this `claude.md` file first for project overview
2. Reference specific documentation files for detailed guidance
3. Use citation system (`[SRC-X]`) to verify claims
4. Follow implementation roadmap phases sequentially

**For Other AI Tools:**
- See `global_session.md` for tool-agnostic context
- Use `03_ai_tools_assistance.md` for AI tool-specific recommendations

---

## Contact & Support

**Documentation Issues:** Check corresponding `.md` files for detailed guidance
**Data Issues:** Refer to `06_data_sources.md` and `08_data_pipeline_compliance.md`
**Model Issues:** Refer to `01_development_pipeline.md` and `nba_metrics_reliability_report.md`

**Last Updated:** September 10, 2026
**Version:** 2.0 (implementation begun)