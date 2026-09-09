# ADR 0001: Python as the orchestration layer

- **Status:** Accepted
- **Date:** 2026-09-10
- **Deciders:** AlphaNerdFx

## Context

A recurring assumption about this project is that it is limited by Python's
speed. It is not. Almost every arithmetic operation in the pipeline already
executes as compiled machine code. Python is the layer that decides *what* to
compute and in *what order*. It is not the layer doing the computing.

The principle that governs this is **Amdahl's Law**, from computer architecture.
The overall speedup available from optimising one component is capped by the
fraction of total runtime that component occupies. If Python accounts for a
fifth of wall-clock time, replacing Python with something infinitely fast makes
the whole system 25 percent faster and no more. Rewriting in Rust to capture
that is an enormous cost chasing a bounded return.

This split has a name in system design: the **two-layer model**, or
orchestration over kernels. It is the same pattern as a shell script driving
compiled utilities, or SQL driving a C++ storage engine. The high-level language
expresses intent. The compiled kernel provides throughput. It has been the
dominant architecture of scientific computing since NumPy, and before that since
MATLAB wrapped LINPACK.

### Where the time actually goes

| Stage | What executes it | Language underneath |
|---|---|---|
| Downloading data | Network wait, rate-limited to 1 request per second | Irrelevant |
| Parquet read and write | Apache Arrow | C++ |
| **Possession and stint parsing** | **CPython interpreter loop** | **Python** |
| Sparse matrix assembly | SciPy sparse | C |
| Ridge solve | LAPACK via SciPy | **Fortran** |
| Gradient boosting baseline | LightGBM | C++ |
| Bayesian fusion model | NumPyro, compiled through XLA | LLVM native |
| Stint aggregation | DuckDB, vectorised execution | C++ |
| Serving predictions | Network wait | Irrelevant |

One row is genuinely Python-bound, and it is the honest concession.
Reconstructing which five players were on the floor requires walking roughly
fourteen million play-by-play events object by object. CPython is somewhere
between 50 and 100 times slower than C at that kind of tight loop. A full
historical backfill plausibly takes tens of minutes where compiled code would
take seconds.

That concession matters less than it appears, for one reason. **The backfill
runs once.** The nightly job parses a single day of games. Optimising a one-time
operation from twenty minutes to twenty seconds is not a reason to change
languages, and "make it work, make it right, make it fast" orders those steps
deliberately.

There is also a detail worth noticing in that table. The ridge solve, the
mathematical core of the entire project, already runs Fortran. LAPACK has been
the reference implementation of dense linear algebra since 1992. The project is
already using one of the fastest languages ever written for its hottest
numerical path. Nobody writes it by hand, which is exactly the point of the
two-layer model.

## Alternatives considered

**R** is the strongest rival, and it beats Python on the statistics. hoopR is
written in R. The sports analytics community lives substantially in R through
nflverse, baseballr and hoopR. For this specific project, glmnet is the
reference implementation of penalised regression, and brms with Stan underneath
is more mature for hierarchical measurement-error models than anything in
Python. The tidyverse is arguably a better-designed data manipulation interface
than pandas. Where R loses is the other half of the goal: deployment through
plumber is far weaker than FastAPI, static typing is essentially absent,
packaging and continuous integration practice is less developed, and the
employment signal outside biostatistics and academia is smaller. R is better
software for statisticians. Python is better software.

**Julia** was created to solve precisely this complaint. Its community calls it
the **two-language problem**: prototype in a slow high-level language, then
rewrite the hot parts in C or Fortran, and now maintain two codebases. Julia's
answer is multiple dispatch plus an LLVM just-in-time compiler, giving near-C
loop speed with high-level syntax. Turing.jl covers probabilistic programming
and DataFrames.jl covers tabular work. It is the best candidate on paper for
this combination of heavy parsing and Bayesian modelling. It fails on ecosystem
and community. There is no `nba_api` and no `pbpstats`, so the scrapers would be
written and maintained here, including every stats.nba.com quirk that community
has already solved. For a project whose stated goal is attracting FOSS
contributors, choosing a language with a small contributor pool is
self-defeating.

**Rust** wins decisively in exactly one place and loses everywhere else. The
possession parser is a genuinely good fit: no garbage collector, memory safety
without runtime cost, and predictable performance. The mature way to use it is
not to rewrite the project but to compile a Python extension module through
PyO3 and maturin. That is how Polars, Ruff, uv, pydantic-core and Hugging Face
tokenizers all work, and several are already dependencies here. As a
whole-project language it fails hard. There is no Stan, no NumPyro, no PyMC, no
SHAP, no MLflow. Linfa is not remotely a substitute for scikit-learn. Markov
chain Monte Carlo would be implemented by hand, which is a research programme
rather than a work item. Add long compile times and a borrow checker that takes
months to internalise.

**Zig** is the weakest candidate. It remains pre-1.0 with no stability
guarantee, and its numerical and statistical library ecosystem is close to
nonexistent. Its genuine strengths, seamless C interoperability, compile-time
metaprogramming, and an excellent cross-compilation story, address problems this
project does not have. Choosing it means implementing basic linear algebra
before writing a single line about basketball.

**C and C++** are where numerical kernels have always lived, and they are
already in the stack indirectly. Stan is C++. DuckDB is C++. LightGBM is C++.
Eigen is the standard C++ linear algebra library. C++ would be written directly
only if SciPy and Eigen could not express something needed, and even then it
would be wrapped in Python through pybind11. The costs are memory unsafety, slow
builds, and a fragmented package management story split between vcpkg and Conan.

**Go** is a real option for two narrow jobs and no others. Concurrent
rate-limited HTTP fetching is genuinely more pleasant with goroutines and
channels than with Python's asyncio, and a single static binary makes a smaller
container image with a faster cold start. Its numerical ecosystem is thin,
gonum notwithstanding, there is no dataframe library worth using, and there is
no Bayesian tooling at all. It never touches the modelling.

**TypeScript and JavaScript** matter for exactly one part of this project. D3
remains the most capable data visualisation toolkit that exists in any language,
with Observable Plot as a friendlier modern layer over it. If the dashboard
outgrows Streamlit, this is where it goes. It is not a modelling language.

**Java** brings strong JVM performance and the most mature build and profiling
tooling of any ecosystem. Its statistical libraries are poor, it has no Stan
equivalent, and it is verbose for exploratory data work. No reason to use it
here.

**Scala** is Spark's native language, and Spark is the right answer when data
exceeds single-machine memory. This play-by-play corpus is roughly 500 megabytes
across 25 seasons, which fits comfortably in laptop RAM. Introducing Spark would
add distributed-systems overhead, serialisation costs and operational complexity
for zero benefit. Worth stating plainly because it is a common and expensive
mistake: reaching for big-data tooling on data that is not big.

**C# and F#** deserve a fairer hearing than they usually get. ML.NET is
competent and F# is genuinely pleasant for numerical work with units of measure
and strong inference. The problem is domain: there is effectively no sports
analytics community there, no equivalent data libraries, no Bayesian tooling,
and therefore no contributors and no portfolio signal in this niche.

**SQL** is the one people skip, and it is already in the stack. The DuckDB
queries doing stint aggregation will be the fastest code in the project, because
SQL is declarative and the query optimiser plus vectorised C++ execution beats
anything written by hand.

**MATLAB** is proprietary, which contradicts the FOSS goal outright. **Mojo** is
still too early and too tied to one vendor to build a contributor community
around.

## Decision

Python is the orchestration layer. Compiled kernels do the computing. No
rewrite is undertaken on intuition.

Adopt additional languages only in this order, and only when the stated trigger
fires:

| Language | Where | Trigger |
|---|---|---|
| **SQL on DuckDB** | Stint aggregation | Immediately, and increasingly as seasons accumulate. Highest speedup per unit of effort, and no new toolchain. |
| **Rust via PyO3** | Possession parser only | Both: the parser is verified against known box scores, **and** a profiler confirms it dominates runtime. |
| **R with glmnet** | Independent second RAPM implementation | Once the Python RAPM produces numbers worth cross-checking. |
| **TypeScript with D3** | Dashboard | Only when Streamlit cannot express what is needed. |
| **Go** | API | Only if traffic exceeds one Python process, which is unlikely for a research metric. |

The R item is not redundancy, it is methodology. Two independent
implementations agreeing is evidence. One implementation agreeing with itself is
not. For a project whose central claim is reproducibility, that is worth more
than any speedup.

## Consequences

**Accepted:** the historical backfill is slower than it could be. It runs once,
so this is tolerated.

**Accepted:** the possession parser is the one genuinely Python-bound stage, and
it stays that way until profiling says otherwise. Optimising an unverified
parser means writing fast wrong answers.

**Gained:** `nba_api`, `pbpstats`, hoopR interoperability, NumPyro, MLflow, SHAP
and scikit-learn, none of which would exist in most alternatives.

**Gained:** a contributor pool. The language choice is an ecosystem decision
more than a performance decision, and for a project seeking contributors the
ecosystem half carries more weight.

## Adjacent projects, for future reference

Not decisions for this project, recorded because the same fundamentals apply:

- **Stan**, a domain-specific language. The measurement-error model expressed in
  Stan is its canonical form, and that skill transfers to every hierarchical
  modelling problem in any field.
- **Julia**, when a project is genuinely compute-bound rather than
  ecosystem-bound. Possession-level Monte Carlo simulation of whole seasons, and
  lineup optimisation over a combinatorial space, are both millions of tight
  loops with little library dependency. That is where Julia's design pays off
  and where the argument against it above stops applying.
- **Rust with Polars, or Scala with Spark**, for one expansion only. Raw optical
  tracking data runs at 25 frames per second, for ten players, across 1,230
  games a season. That is terabytes, and it is the single direction where this
  project's data stops fitting on a laptop.
- **Elixir or Go**, for a live in-game ingestion service. Many concurrent
  long-lived connections with modest computation per message is what the BEAM
  virtual machine's supervision trees are built for.
- **C++**, for a custom Stan model extension or a custom DuckDB extension. Both
  are C++ plugin architectures.

## Summary

The language whose job is orchestrating compiled kernels was chosen for a
problem that is mostly compiled kernels plus a great deal of ecosystem. That is
the correct trade, and the ecosystem half is doing more work in that sentence
than the performance half. The time to revisit it is when a profiler points at
Python, not when intuition does.
