# Continuous integration

Two pipelines run against every change. `ci.yml` answers **does the code run**.
`rigour.yml` answers **are the numbers right, stable, and still fast**.

For a scientific project the second question matters more, and almost no
general-purpose tooling asks it.

---

## Mutation testing

**What it is.** A tool that edits your source code on purpose, then runs your
test suite against the edited version. It flips a `<` to a `<=`, turns a `+`
into a `-`, replaces a constant with zero. Each edit is called a *mutant*. If a
test fails, the mutant is *killed*, which means that line was genuinely checked.
If every test still passes, the mutant *survived*, which means no test actually
verifies that line.

**Where it comes from.** Fault-based testing, from Richard Lipton's 1971
proposal and the DeMillo, Lipton and Sayward work that followed. The underlying
principle is the *competent programmer hypothesis*: real defects are usually
small deviations from correct code, so deliberately introducing small deviations
approximates the defects you would actually make. It is the same design
philosophy as fault injection in distributed systems and as chaos engineering.
You do not wait for the failure, you cause it and observe.

**Who uses it and why.** Safety-critical software first: avionics under DO-178C,
medical devices, automotive under ISO 26262, where a regulator wants evidence
that tests are adequate rather than merely present. It has since spread to
compiler and database development, where a subtle wrong answer is worse than a
crash, and into mainstream backend engineering through tools like PIT for Java
and Stryker for JavaScript.

**Why it applies here.** Coverage is a poor proxy for test quality in numerical
code. A test asserting that a ratings array has 450 entries executes the entire
solver and verifies nothing about the numbers in it. That test yields excellent
coverage and catches no bug. Mutation testing is the only automated way to tell
those two situations apart, and this project's whole output is numbers.

**What it costs.** Time. The suite runs once per mutant, so a hundred mutants
means a hundred suite runs. It is scheduled weekly rather than per commit for
exactly that reason. It is currently reported rather than enforced; enforcement
begins once the RAPM solver lands.

```bash
make mutants
```

### Baseline

The first run on the week-0 codebase generated 93 mutants and killed 62, a
mutation score of 67 percent. Investigating the survivors exposed five real
gaps, all since closed:

| Survivor | What no test checked |
|---|---|
| Error message emptied | That an unknown stage name lists the valid ones |
| `parents=True` removed | That a data root several levels deep is created in full |
| `PYTHONHASHSEED` key corrupted | That seeding pins Python's string-hash salt |
| `exist_ok=True` flipped | That creating a stage directory twice does not raise |
| `create` default flipped | That resolving a path has no side effect |

Not every survivor is a defect. Two categories never die:

- **Equivalent mutants**, where the change cannot alter behaviour. Rewriting
  `encode("utf-8")` as `encode("UTF-8")` is one: Python codec names are
  case-insensitive.
- **Environment-dependent mutants**, where the change matters on one platform
  and not another. Renaming the `data` directory to `DATA` survives on a
  case-insensitive filesystem such as Windows and dies on Linux, which is why
  the scheduled run happens on Linux.

A mutation score below 100 percent is therefore normal and expected. The number
is a prompt to investigate, not a target to hit.

---

## Benchmark regression tracking

**What it is.** Timings recorded for chosen operations on every run, stored, and
compared against previous runs. A change that makes something meaningfully
slower gets a comment on the pull request.

**Where it comes from.** Statistical process control, brought into software as
performance regression testing. The principle is that performance is a
*specification*, not a side effect. If a number is not asserted, it is free to
drift, and drift is only ever noticed once it becomes a crisis.

**Who uses it and why.** Compiler and runtime teams live on it: LLVM, V8, CPython
and the Rust compiler all run continuous benchmark suites, because a two percent
regression per release compounds into an unusable product. Database engines and
game engines do the same.

**Why it applies here.** The RAPM design matrix across twenty seasons is large
and mostly zeros. It only works because it is stored sparsely. A careless change
that materialises it as a dense array turns a thirty-second solve into an
out-of-memory crash. That failure looks mysterious when it appears and obvious
when a chart shows the exact commit where timing jumped.

**What it costs.** Almost nothing per run, plus some noise: shared CI machines
give variable timings, so the alert threshold is set loosely at 150 percent to
avoid crying wolf.

```bash
make bench
```

---

## The determinism check

**What it is.** A job that runs the same computation twice and asserts the two
results are byte-identical, and compares the result against a stored
*fingerprint*, a short hash of the output table.

**Where it comes from.** Reproducible builds, from the Debian and Bitcoin
communities, and before that from the scientific replication crisis. The
principle is that a result nobody can recompute is a claim, not a measurement.

**Who uses it and why.** Security-sensitive distribution first: reproducible
builds let anyone verify that a binary really came from the published source.
Scientific computing adopted the same idea to make published results checkable.

**Why it applies here.** Nondeterminism creeps into numerical Python quietly.
Thread scheduling changes floating point summation order. An unseeded bootstrap
gives different standard errors each run. Python salts string hashes per process,
so iterating a set of player names has no fixed order. Any of these makes your
published metric unreproducible while every test still passes.

`pippen.repro` provides the two tools this depends on: `set_global_seeds` pins
every random source, and `fingerprint` reduces a table to a stable sixteen
character hash that ignores row and column order but not values or dtypes.

**What it costs.** One extra CI job, and the discipline of seeding anything that
samples.

---

## Random test ordering

**What it is.** Running the test suite in a shuffled order rather than the order
the files happen to sit in.

**Where it comes from.** Test isolation, a core unit-testing principle: each test
must set up and tear down its own state. Shuffling is the cheapest way to detect
a violation.

**Who uses it and why.** Widely, once a suite gets large enough that a test
passing only because an earlier test left something behind becomes common. Ruby
on Rails made randomised ordering the default for this reason.

**Why it applies here.** Data pipelines cache aggressively. A test that writes a
Parquet file into a shared directory and a later test that reads it will pass in
file order and fail in any other. Shuffling catches that on the first run rather
than six months later.

**What it costs.** Occasional confusing failures that turn out to be real bugs.

---

## Lockfile drift

**What it is.** A check that `pyproject.toml` and `uv.lock` still agree.

**Where it comes from.** Configuration management and the principle of a single
source of truth. A declared dependency and a resolved dependency are two
statements about the same thing, and two statements can disagree.

**Who uses it and why.** Anyone shipping software that must build identically
twice. It is the same instinct behind checked-in `package-lock.json`,
`Cargo.lock` and `poetry.lock`.

**Why it applies here.** Reproducibility is the project's central claim. A
dependency added to `pyproject.toml` without relocking means the next person to
clone the repository gets a different version of scipy, and possibly different
numbers in the final metric.

**What it costs.** Seconds.

---

## Pinning actions

**What it is.** Every `uses:` line in a workflow names a third-party action and a
git ref. That ref decides which code GitHub downloads and runs with access to
the repository.

**Where it comes from.** Dependency pinning, and the same reproducibility
argument that motivates a lockfile. A reference that can change under you is a
build that can change under you.

**Who uses it and why.** Anyone whose CI can publish artifacts. Supply-chain
attacks on build systems work precisely by altering what a mutable reference
points at, which is why OpenSSF Scorecard checks for it.

**Why it applies here.** The first three runs of this project failed on
this, in two different ways:

- `astral-sh/setup-uv@v10` resolved to nothing. Version 10.0.1 exists as a
  release, but Astral stopped publishing bare major tags after v7. **A release
  existing does not mean a matching major tag exists.**
- `benchmark-action/github-action-benchmark@v1` had never been valid. That
  project publishes only full version tags.

Check the tag list, not the release feed:

```bash
gh api repos/OWNER/NAME/tags --jq '.[].name' | head
```

**What it costs.** Exact pins do not receive patches automatically, and with
Dependabot disabled here they are bumped by hand. That is why the two actions
without major tags are pinned exactly and the rest track a major.

## Scheduled data refresh

`ci.yml` and `rigour.yml` both run against every change. `refresh-data.yml` runs
on a clock instead: it exists to answer a question neither of those can, which
is whether the *data*, not the code, is still current.

**What it is.** A workflow that runs on a cron schedule rather than on a push
or pull request. GitHub Actions triggers it at a fixed time regardless of
whether anything in the repository changed, in addition to a manual
`workflow_dispatch` trigger for an on-demand run.

**Where it comes from.** The `cron` job, from Unix system administration:
a daemon that wakes up on a schedule and runs a command, used since the 1970s
for anything that needs to happen periodically without a human remembering to
start it. GitHub Actions' `schedule` trigger is that same idea, hosted.

**Who uses it and why.** Any pipeline that ingests from a source outside its
own control: a nightly ETL job pulling from a partner API, a scraper checking
for new listings, a security scanner re-running against yesterday's
dependencies to catch a vulnerability disclosed after the last commit. The
common thread is that the check has nothing to do with a code change and
everything to do with time passing.

**Why it applies here.** `pippen`'s own tests and lint checks say nothing about
whether `data/raw/` reflects last night's games. hoopR publishes new
`play_by_play`, `player_box` and `team_box` files, and updates the master
schedule, on its own timetable, not this repository's. Without a scheduled
job, staleness is silent: nothing about a green `ci.yml` run tells anyone that
the cached data is three weeks old. `refresh-data.yml` re-downloads the
current season with `--force` and runs `pippen validate` against the result,
so a broken or stale upstream file turns into a failed GitHub Actions run
instead of an unnoticed gap.

The workflow determines "current season" from the run date rather than a
hardcoded year, using the season-end-year convention documented in
`hoopr.py`: a season that starts in October of year Y-1 is labelled Y, and it
keeps that label through the following September. It schedules at 13:00 UTC,
chosen as a buffer past the latest West Coast games can plausibly finish,
since hoopR's own publish time is not documented in any source this project
cites; if a run is ever caught missing the previous night's games, that hour
needs pushing back, and the workflow says so in its own comments.

On a validation failure, the job fails and uploads the validation report as
an artifact, and nothing is cleaned up afterward. Both halves of that follow
from the same fact: the runner is a fresh virtual machine that GitHub destroys
at the end of the job. A partially-fetched season sitting in `data/raw/` when
the job ends costs nothing, because that filesystem never persists and this
workflow never commits from it, data never enters git regardless.

**What it costs.** A scheduled job runs whether or not anything needed
refreshing, which spends runner minutes during the season even on nights when
hoopR published nothing new; `pippen fetch --force` cannot tell the
difference in advance, only after redownloading. The schedule is also a
guess about hoopR's publish time rather than a documented fact, so it may
need retuning once real failures show the actual cadence.

## Dependency updates

Dependabot's automated pull requests are switched off deliberately, so that every
commit in this repository has a human author. Dependabot **security alerts** stay
enabled, because an alert notifies without committing anything.

Updates are applied by hand, monthly:

```bash
make upgrade
make check
```
