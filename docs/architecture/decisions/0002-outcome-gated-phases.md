# ADR 0002: Outcome-gated phases instead of time-boxed weeks

- Status: Accepted
- Date: 2026-09-10
- Deciders: AlphaNerdFx

## Context

The original roadmap divided twelve weeks of work into nine numbered phases. Week
0 was planned as one week and finished in thirteen hours, across eighteen
commits, using agents working in parallel on disjoint files.

The obvious response is to divide every remaining estimate by seven. That would
be wrong, and the composition of Week 0 shows why.

| Category | Lines produced |
|---|---|
| Documentation | 3,182 |
| Configuration and CI | 732 |
| Tests | 474 |
| Product code | 202 |

Roughly 85 percent of the output was documentation and configuration. That work
is well specified, has no external dependencies, is verifiable by a linter or a
schema, and splits cleanly across files. Those four properties are exactly what
makes work compressible by agents.

The remaining phases do not share those properties.

### What actually limits each kind of work

**Network-bound work does not compress at all.** This project is bound by a
compliance rule of one request per second to stats.nba.com. Possession data for
stint extraction needs play-by-play per game, and the floor is arithmetic:

| Scope | Requests | Wall-clock floor |
|---|---|---|
| 2015 to 2024, one request per game | 12,300 | 3.4 hours |
| 2015 to 2024, two requests per game | 24,600 | 6.8 hours |
| 2002 to 2026, one request per game | 30,750 | 8.5 hours |
| 2002 to 2026, two requests per game | 61,500 | 17.1 hours |

Twenty agents finish that in the same time as one. The constraint is a rule this
project chose to honour, and honouring it costs hours that no amount of
parallelism recovers.

**Compute-bound work compresses only with better algorithms.** A cross-validated
ridge solve over a sparse design matrix with a couple of thousand player columns
and millions of stint rows, bootstrapped for standard errors, is CPU time. More
agents writing code does not shorten it.

**Judgement does not compress.** The RAPM validation gate asks whether a computed
metric agrees closely enough with a published one to be trusted. If it does not,
somebody has to decide between debugging and switching the target variable. That
is a decision, not a task.

**Review capacity moves in the wrong direction.** The maintainer is the human
checker. Agents raise the volume of code needing review without raising the
capacity to review it. Past a point, more agents make the bottleneck worse rather
than better.

## Decision

Replace numbered weeks with phases gated by verifiable outcomes.

Each phase declares:

1. **Entry condition.** What must be true before it can start. This makes the
   dependency graph explicit, so what can run in parallel is visible rather than
   guessed.
2. **Definition of done.** A condition a machine or a person can check, not a
   feeling that the phase seems finished.
3. **What limits it.** One of: agent-parallel, network-bound, compute-bound,
   judgement, or review-bound. This says directly whether adding agents helps.

Time estimates are dropped. They were fiction before Week 0 and they are fiction
at a different scale now. A phase is finished when its exit condition holds.

## Consequences

**Gained:** the dependency graph is explicit, so parallelism is a scheduling fact
rather than an aspiration. A phase that says network-bound will not have four
agents thrown at it.

**Gained:** progress becomes checkable. "Phase 2 is done" now means a specific
correlation cleared a specific threshold, rather than a week having elapsed.

**Lost:** no calendar date to point at. For a solo research project with no
external deadline this costs little, and a date derived from fictional estimates
was never worth pointing at.

**Accepted:** some phases will take longer than the week they replaced. The
network floor above is roughly a working day of waiting on its own, and pretending
otherwise would only move the surprise later.
