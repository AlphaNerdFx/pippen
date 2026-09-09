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

## Dependency updates

Dependabot's automated pull requests are switched off deliberately, so that every
commit in this repository has a human author. Dependabot **security alerts** stay
enabled, because an alert notifies without committing anything.

Updates are applied by hand, monthly:

```bash
make upgrade
make check
```
