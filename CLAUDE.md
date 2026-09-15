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

## Writing Style

Applies to documentation, commit messages, code comments, and replies to the
maintainer.

- No em dashes anywhere. Use a comma, a full stop, or restructure the sentence.
- Bold sparingly. If most paragraphs carry bold, none of it carries weight.
  Reserve it for the single thing a reader must not miss on a page.
- Technical and professional, but recognisably written by a person.
- Avoid the contrast-reveal construction. Sentences shaped like "it is not about
  X, it is about Y" or "this was not caused by X, it was actually Y" read as
  generated. State the thing directly and let the contrast be implied.
- Avoid filler openers: "it is worth noting", "at the end of the day", "the key
  insight here", "there are several ways to look at this".
- Prefer concrete nouns and verbs to abstractions. Name the file, the function,
  the number.

---

## Explaining Concepts and Tools

The five-part structure above is the floor, not the ceiling. When a tool or
concept is introduced into this codebase, the explanation carries all of the
following.

1. **The full run-up.** Trace the idea from where it started to what it is now.
   A one-paragraph catch-up is not enough. The maintainer should be able to
   reason about the tool in situations this project has not met yet.
2. **Historic origin.** Which older technology or idea it descends from, and
   what problem that older thing existed to solve. Understanding the ancestor
   explains the shape of the descendant.
3. **Concurrent usage.** Which areas of software and AI development use it at
   the same time, and for what. This is what tells the maintainer whether the
   skill transfers to a job.
4. **Feature-level justification.** Not "we use MLflow" but which MLflow
   features, for which purpose, and why those rather than other MLflow features
   or a competing tool. Name what was rejected and why.
5. **Code from this repository.** Show the actual snippet from this codebase,
   not a generic example, and walk through the parts that matter.
6. **Intersections.** When the tool meets other code here, explain both sides
   and why the combination is better than either alone.

---

## Keeping the Project in Scope

Three skills are used deliberately and repeatedly, not just when asked.

| Skill | When | Why |
|---|---|---|
| `/professor` | The moment a concept enters the code | The maintainer learns it while the code that uses it is in front of them, in conversation, with nothing written to disk |
| `/teach` | After each significant implementation | The stateful counterpart, building lessons and records across sessions |
| `/grill-me`, `/grilling` | Before building anything non-trivial | Stress-tests a plan while changing it is still cheap |

The `teach` skill writes a stateful workspace (`MISSION.md`, `lessons/`,
`reference/`, `learning-records/`) into its working directory. Run it with the
working directory set to `docs/learning/` so a public repository root does not
fill up with teaching scaffolding.

---

## Sub-agent Orchestration

Agents run in parallel when their file scopes are disjoint, sequentially when
they are not. Two constraints are real and neither is negotiable.

- **Disjoint file scope.** Two agents editing the same file in one working tree
  will clobber each other. Assign each agent an explicit list of files it may
  touch, and tell it to report rather than edit anything outside that list.
- **Staggered verification.** Concurrent `uv` invocations contend for the same
  environment and lockfile. Two agents running the test suite at the same moment
  can have one killed. Let agents implement in parallel, then verify in turn.

After each agent finishes: run `/code-review` on its changes, then `/teach` on
what the implementation demonstrates. Only then commit.

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

**Current Status:** Phases 0 through 3 are complete. 508 tests, mypy strict clean,
documentation building strictly.

RAPM is computed from data.nba.com possessions for NBA 2016-17 to 2024-25 and
clears its gate at Spearman 0.914 against an independently built stint dataset.
Metric reliability is measured across all 25 hoopR seasons rather than assigned.
The fusion model is fitted and calibrated at 90.9 percent against a nominal 90.

**The claim under test has been answered, and the answer is no.** Fusing public
metrics does not predict next-season team net rating better than RAPM alone, and
is not distinguishable from it (p = 0.171). Ridge and tuned LightGBM over every
metric land in the same place, so the ceiling belongs to these inputs. See
`docs/methodology/claim-under-test.md`.

Three findings shape what comes next. Box-score metrics are dominated by
position, so a one-factor model of them recovers player size. Reliability runs
against validity across the metric set at r = -0.564, which is why nothing in
this codebase turns reliability into a weight. And the fusion's intervals are a
floor on the true uncertainty, because pinning the anchor also pins its residual
scale; `docs/methodology/calibration.md` names the fix.

Phases are now gated by outcomes rather than dates. See
[ADR 0002](docs/architecture/decisions/0002-outcome-gated-phases.md) for why, `TODO.md`
for the roadmap, and `.context/HANDOVER.md` for current state.

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

Contradictions inside the research itself are catalogued in
`docs/methodology/errata.md`. The research files are **never edited**, so the
errata is where corrections live. The three that affect day-to-day work:

- **RAPM is Tier 2, not Tier 1.** Corrected above. Both research reports file it
  under Tier 2 at 80-85%, which their own boundaries require. RAPM is the
  project's ground truth, so the overstatement would have flowed downstream.
- **Tier labels were applied inconsistently.** D-EPM and D-RAPM both score
  80-85%, yet one is labelled Tier 1 and the other Tier 2. The tiers were
  assigned by impression and numbered afterwards, which is the strongest single
  argument for measuring reliability rather than citing it.
- **0.44 is not an arbitrary constant, and the criticism of PER is wrong.** It
  estimates the fraction of free throw attempts that consume a possession, since
  a two-shot foul ends one possession rather than two and an and-one ends none.
  The same constant serves the same purpose in Pace, TOV%, TS% and USG%. It is
  **not** the two-versus-three adjustment; that is eFG%'s `0.5 × 3PM`. The real
  objections to PER, which stand on their own, are box-score-only defence, no
  context adjustment, fitted event weights, and forced renormalisation to 15.

**Consequence for the pipeline:** the legitimate version of the complaint is that
the true fraction drifts with rule changes, and it applies to every metric rather
than to PER. **Measure the possession coefficient per season** from play-by-play
rather than hard-coding 0.44, and treat the fixed value as the baseline.

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

**Skills** in `.claude/skills/`: `refresh-data`, `add-metric`, `release`, `professor`.

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


## Teaching Packet
1. What was built?
2. Why this architecture?
3. Alternatives rejected?
4. What concepts did I just use?
5. What would break at 10× scale?
6. What security issues exist?
7. What production problems could occur?
8. What should I now be able to explain?
9. 5 questions for me
10. One modification I must implement myself
---

## Contact & Support

**Documentation Issues:** Check corresponding `.md` files for detailed guidance
**Data Issues:** Refer to `06_data_sources.md` and `08_data_pipeline_compliance.md`
**Model Issues:** Refer to `01_development_pipeline.md` and `nba_metrics_reliability_report.md`

**Last Updated:** September 10, 2026
**Version:** 2.0 (implementation begun)