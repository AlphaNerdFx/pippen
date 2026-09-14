# 0001: What the data layer taught

Phase 1 produced four modules and 265 tests. Four ideas inside it transfer to
work that has nothing to do with basketball, and this note takes each one from
its origin to the line of code in this repository that uses it.

---

## 1. Atomic write: rename is the only safe commit

### The full run-up

A program that writes a file has a window where the file exists but is
incomplete. If the process dies inside that window, what is left on disk is a
truncated file that looks, to everything downstream, like a finished one.

The operating system gives exactly one operation that has no such window.
`rename(2)` on POSIX replaces one directory entry with another. It either
happened or it did not, and no reader ever sees a half-state. It has been
atomic since early Unix, and the guarantee holds only when both paths are on
the same filesystem, because a cross-filesystem rename is really a copy
followed by a delete, which brings the window straight back.

So the pattern is: write to a temporary file next to the destination, make sure
the content is complete and correct, then rename it over the target.

### Where it comes from

Journalling filesystems and database write-ahead logs use the same reasoning.
A database does not mutate a page in place and hope. It writes the intent
somewhere durable, then flips one pointer. Git does this too: an object is
written to a temporary name, hashed, then linked into place. The shared
ancestor is the idea that durability comes from ordering, not from speed.

### Who uses it and why

Package managers, configuration management, deployment tooling, any daemon that
rewrites a config file while something else might read it. The problem it
solves in all of them is identical: a reader must never observe a partial
write, and a crash must never leave one behind.

### Why it applies here

A truncated Parquet file is worse than a missing one. The downloader skips
files that already exist, so a partial download would be skipped on the next
run and silently feed every calculation downstream. That is a wrong answer with
no error attached to it.

### The code

From `src/pippen/data/hoopr.py`:

```python
def _download_atomically(
    session: requests.Session, url: str, target: Path, *, timeout: float
) -> str | None:
    # Same filesystem as the destination, so the final move is an atomic rename
    # rather than a copy that could itself be interrupted.
    file_descriptor, tmp_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".part"
    )
    os.close(file_descriptor)
    tmp_path = Path(tmp_name)

    try:
        _download(session, url, tmp_path, timeout=timeout)
    except (TransientDownloadError, requests.HTTPError) as exc:
        tmp_path.unlink(missing_ok=True)
        return f"download failed: {exc}"

    if not _is_valid_parquet(tmp_path):
        tmp_path.unlink(missing_ok=True)
        return "downloaded file failed the parquet integrity check (likely truncated)"

    tmp_path.replace(target)
    return None
```

Three details carry the weight. `dir=target.parent` puts the temporary file on
the same filesystem, without which `replace` silently degrades to a copy. The
integrity check runs on the temporary path, before the rename, so a truncated
download never reaches the destination. And every failure path unlinks the
temporary file, so a failed run leaves the directory exactly as it found it.

### What it costs

Briefly twice the disk space, and a small amount of care to keep the temporary
file on the right filesystem. Both are cheap next to the failure it prevents.

---

## 2. The check-then-act race, and why the lock spans the sleep

### The full run-up

A rate limiter records when the last request went out and, on the next call,
sleeps for whatever is left of the interval. Written naively it reads the
timestamp, decides, then sleeps. Those are three steps, and a second thread can
arrive between any two of them.

Two threads each read the same "last call was 0.9 seconds ago", each decide
independently that 0.1 seconds of waiting is enough, and both proceed. The
limiter is now letting two requests through where it promised one.

This is the check-then-act race, and it is the same shape as the one that makes
`if not os.path.exists(p): open(p, "w")` unsafe. The check and the act are
separate operations, and the world can change between them.

### Where it comes from

Dijkstra's work on mutual exclusion in the 1960s, and the critical section it
produced. The rule that came out of it is that operations which must appear
indivisible have to be made indivisible, by putting them inside one lock rather
than by hoping the window is too small to matter.

### Who uses it and why

Every connection pool, every token bucket in an API gateway, every distributed
lock. The failure is always the same: something that was supposed to happen
once happened twice, under load, intermittently, and not in testing.

### Why it applies here

The project's compliance rule is one request per second to stats.nba.com.
Breaching it risks the endpoint being blocked for every user of the package,
not only for this process. A limiter that leaks under concurrency would breach
it exactly when traffic is highest.

### The code

From `src/pippen/data/nba_api.py`:

```python
def wait(self) -> None:
    with self._lock:
        now = self._clock()
        if self._last_call is not None:
            remaining = self._min_interval - (now - self._last_call)
            if remaining > 0:
                self._sleep(remaining)
                now = self._clock()
        self._last_call = now
```

The lock is held across the sleep, not released around it. That is the part
people get wrong, because holding a lock while sleeping looks wasteful. Here it
is the entire point: only one thread can be inside `wait` at a time, so calls
are paced regardless of how many threads share the limiter. A blocked thread
waits on the lock rather than doing useful work, which is the correct trade for
a component whose only job is to make callers wait.

`clock` and `sleep` are injected rather than called directly. That is what lets
the tests drive a fake clock and assert exact values, instead of sleeping in
real time and asserting something vague about elapsed duration.

### What it costs

Throughput. A limiter built this way cannot be faster than its interval, by
construction. If a use case ever needs parallel fetching, the answer is several
limiters against several hosts, not a leakier lock.

---

## 3. Validation at the boundary, and the third outcome

### The full run-up

Input validation at the edge of a system is old. What is less obvious is that a
validation result has three states, not two.

A check can pass. A check can fail. A check can also be unable to run, because
an input it needed was absent. Collapsing that third case into "pass" produces
a green report for data nobody looked at, which is worse than having no report,
because it carries the authority of a check that never happened.

### Where it comes from

Design by contract, from Bertrand Meyer and Eiffel in the 1980s: preconditions
a caller must satisfy, checked at the boundary rather than deep inside. The
three-state result is closer to the tri-state logic that SQL uses for NULL,
where unknown is deliberately not the same as false.

### Who uses it and why

Data engineering broadly. Great Expectations, dbt tests, Monte Carlo and
similar tools exist because a bad row does not raise an exception. It produces
a plausible number. Schema registries in Kafka do the same job at the message
boundary.

### Why it applies here

Two layers were needed, and separating them is the interesting part. A schema
sees one table and checks columns, dtypes and per-row constraints. It cannot
see that a play-by-play file is missing forty games, because that file is
internally perfect. Only a check that reads the schedule alongside it notices.

### The code

From `src/pippen/data/validate.py`:

```python
@dataclass(frozen=True)
class CheckResult:
    check: str
    status: CheckStatus
    detail: str

    @property
    def ok(self) -> bool:
        """Whether this check found nothing wrong.

        A skip counts as not ok. It did not find a problem, but it also did not
        look, and treating those the same is how unchecked data reaches a
        calculation.
        """
        return self.status == "passed"
```

The `ok` property is where the idea becomes enforceable. Anything downstream
that asks "was this fine" gets `False` for a skip, so a missing input cannot be
mistaken for a clean result by code that was not paying attention.

### The intersection worth noticing

The two layers compose rather than duplicate. `schemas.py` guarantees that a
frame reaching `validate.py` has the columns and dtypes it expects, so the
cross-table checks can be written without defensive column-existence guards
everywhere. Each layer is simpler because the other exists.

### What it costs

Two modules where one might seem enough, and the discipline to keep per-column
checks out of the cross-table layer.

---

## 4. Why a test written after the code can lock in a bug

### What happened, in this repository, this week

An agent wrote a lookahead that scans forward from a missed free throw for the
rebound that settles it. It skipped substitutions and stopped at anything else.
That was wrong: a foul call or a replay review sitting one event before a clear
rebound label made the whole trip unresolvable.

Reviewing its output, I wrote a test:

```python
def test_a_non_substitution_between_the_miss_and_the_rebound_blocks_resolution():
    ...
    assert result.excluded_unresolved == 1
```

That test passed. It was also wrong, because it asserted the buggy behaviour as
correct. I had read the implementation, understood what it did, and written a
test confirming it did that.

### Why this is structural rather than careless

A test written after an implementation, by whoever read that implementation,
tends to encode what the code does rather than what it should do. The
requirement was "find the rebound that settles this free throw". The code did
"skip substitutions, stop at anything else". Reading the code makes the second
one feel like the requirement.

Mutation testing does not save you here. It checks that a test is sensitive to
changes in the code, and this test was. It cannot check that the behaviour the
test asserts is the behaviour that was wanted.

### What did catch it

An independent reviewer, working from the specification rather than from the
code, with access to the real data. It pulled all 29 excluded rows and found
every one had an unambiguous rebound label within four events. It also found
the exclusions clustered by event type, six coach's challenges and seven runs
of three substitutions, which made them systematic bias rather than noise.

### The practical rule

Write the assertion list before the implementation, as test names with no
bodies. The names come from the requirement, before any code exists to bias
them. Write the bodies afterwards. That keeps the workflow this project uses,
implement then test, while removing the specific failure mode above.

For anything with an external ground truth, possessions reconciling to official
box scores, or a computed metric matching a published one, write the check
first. Those are the specification, and they come from outside the repository
entirely, so there is nothing for an implementation to bias.

---

## What Phase 1 is worth on a CV

Every idea above appears in job descriptions under a different name.

| Here | Named elsewhere as |
|---|---|
| Atomic write then rename | Crash-safe persistence, idempotent writes |
| Lock spanning the sleep | Thread safety, race condition, critical section |
| Bounded retry with backoff | Resilience, fault tolerance, circuit breaking |
| Schema at the boundary | Data contracts, data quality, schema enforcement |
| Skip is not pass | Observability, avoiding false-green monitoring |
| Review against spec, not code | Independent verification, adversarial review |

The transferable skill is not the basketball. It is knowing why the rename goes
last, why the lock stays held, and why a green check that never ran is the most
dangerous result a pipeline can produce.
