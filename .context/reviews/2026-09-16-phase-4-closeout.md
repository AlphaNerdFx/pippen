# Code review, Phase 4 closeout

Two-axis review of `git diff da89992...HEAD`, run 16 September 2026. 1,242 diff
lines across 15 files.

Scope: freezing the public API in `src/pippen/published.py`, shipping the
computed tables inside the wheel, the size-capped exemption to non-negotiable
rule 1, citation metadata, and `scripts/setup_publishing.sh`.

The stakes shaped the brief. A version published to PyPI can be deleted but
never re-uploaded, so a defect that ships is not fully recoverable, and both
agents were told to weight findings that would only fail on someone else's
machine after publication.

Not an issue tracker. This is the record of what was found and what was decided.

---

## Standards axis

| # | Standard | Where | Status |
|---|---|---|---|
| S1 | `CONTRIBUTING.md` > Shell scripts and CI steps > never poll in a loop | `setup_publishing.sh`, the 8-iteration PyPI check | Closed |
| S2 | `README.md` documents `./scripts/setup_publishing.sh` | File mode was `100644`, so the documented command returns "Permission denied" | Closed, now `100755` |
| S3 | `CLAUDE.md` > Writing Style > name the file, the function, the number | `published.py`, a `#:` doc-comment sat above `_DATA_PACKAGE` while describing `_DATA_DIRECTORY` | Closed |

S1 is the one worth arguing about. The loop was bounded at eight iterations, so
the hang rationale in the rule's own justification did not apply. The rule's
first sentence prohibits the shape rather than the unboundedness, and the script
narrated the wait in its output, which is what drew the agent's eye. The
replacement is a single `timeout 20 curl`, matching the "Right" example in
`CONTRIBUTING.md` exactly.

The deciding argument was not the standard. Stage 2 recommends a required
reviewer on the `pypi` environment, which holds the publish job until a human
approves it, so in the recommended configuration a two-minute poll always times
out and prints the "not visible yet" branch. The loop was waiting for something
it could not see arrive.

ADR 0006's format conforms to 0001-0005. Sixteen bold markers against 10-12 in
the neighbouring ADRs, which is a judgement call rather than a breach. No em
dashes in the diff. The rule 1 exemption is adequately justified: the cap is
real, it was applied retroactively to the two pre-existing prefixes, and 1 MiB
is narrow against payloads of 42 KB and 228 KB.

### Baseline smells

| Smell | Where | Decision |
|---|---|---|
| Primitive Obsession | `0.1.0` hard-coded seven times in stage 5 | Closed. `VERSION` is read from `src/pippen/__init__.py`, which is also hatchling's version source, so the tag cannot disagree with the wheel |
| Hidden coupling | `ENV_FILE="${ENV_FILE:-.env}"` plus bare `git tag` assumed the caller's cwd was the repository root | Closed, the wizard cd's to its own parent |
| Speculative Generality | `ask`, `ask_secret`, `set_secret`, `set_var` and `WRITTEN_SECRET` have no call site | Open by decision, see below |
| Duplicated Code | stage 3's inline `mktemp`/`grep -v`/`mv` re-implements the deletion half of `write_env` | Open, one call site |
| Dead constant | `RAPM_WINDOW` was defined, documented, never read and never exported | Closed, deleted |

The dead library helpers stay. `.claude/skills/wizard/SKILL.md` says the library
above the `STAGES` marker is identical in every wizard and is never hand-edited,
and that consistency is the reason it exists. Deleting the unused half would
make this wizard's library diverge from the next one's. The tension between that
instruction and the smell is real and is recorded here rather than resolved.

`RAPM_WINDOW` went because the invariant it recorded is already enforced.
`tests/unit/test_published.py::test_every_window_covers_three_seasons` asserts
the span against the shipped table itself, so a constant carrying the same fact
could only drift away from it.

---

## Spec axis

| # | Finding | Status |
|---|---|---|
| P1 | Stage 5 printed the branch and gated on nothing. A feature branch or detached HEAD would tag and push, and `release.yml` fires on `tags: ["v*"]` | Closed |
| P2 | `ENV_FILE` is relative and the script never cd'd, so running it from `scripts/` would grep a non-existent `.env`, print "no PYPI_TOKEN line", and mark the step done | Closed |
| P3 | `no_data_commits.py` sized the worktree file rather than the staged blob | Closed, see below |
| P4 | `mark_done PIPPEN_SETUP_RELEASED` fired on the tag push, so a declined review recorded a release that never happened | Closed, renamed `PIPPEN_SETUP_TAGGED` |
| P5 | `.zenodo.json` carried no `version` key | Closed |
| P6 | `CITATION.cff` records `date-released: 2026-09-16`, a date that precedes the release it names unless the tag goes out the same day | Closed by a gate, not by an edit |
| P7 | `README.md` claimed "Status: 0.1.0" before 0.1.0 existed on PyPI | Closed |

P4 was closed by renaming rather than by moving the call. The tag push is the
irreversible act and it did happen, so re-running must not re-tag. The marker
now records what it can vouch for.

P6 cannot be fixed by writing a date, because the right date is only known at
tag time, and editing a committed file during stage 5 would dirty the tree that
the same stage requires to be clean. Stage 5 now compares `date-released`
against today before the clean-tree gate, so there is room to correct and commit
before tagging.

### P3, the one that mattered

`size = path.stat().st_size` measured the file on disk. The commit records the
index, and `git add season.parquet && truncate -s 0 season.parquet` presents a
zero-byte file to the check while the index still holds the payload. The hook
guards the rule that data never enters git, and that rule cannot be un-broken
once a commit lands.

Fixed by sizing the staged blob through `git cat-file -s :<path>`, which reads
the index entry. A path with no index entry returns `None`, which is what a
staged deletion looks like, and deletions stay allowed.

**That fix opened a second hole, which review did not find and re-testing did.**
A name spelled `src/pippen/_data/../../../data/season.parquet` matches the
exempt prefix, and git refuses to resolve it against the index, so `_staged_size`
returned `None` and the hook allowed it. The old worktree `stat` had caught this
case by following the traversal on disk. The Spec agent had verified traversal
safety against the code as committed, and that verification stopped being true
the moment the sizing changed. Closed by collapsing the path with
`posixpath.normpath` before matching any prefix, so the traversal resolves to
`data/season.parquet` and falls outside every exemption.

The hook had no tests at all, which is how a bug in the enforcement of a
non-negotiable rule survived its own review. It now has eight, in
`tests/unit/test_no_data_commits.py`, covering the cap, the truncate bypass,
staged deletions, traversal and absolute paths. Both fixes were mutation-checked
by reverting each behaviour in turn and confirming the matching test fails.

---

## Verified, not taken on trust

The Spec agent checked these against a built artifact rather than by reading:

- Cache isolation holds. Mutation, column addition and in-place rename on a
  returned frame all fail to reach the `lru_cache`d original.
- A clean Python 3.10 venv installing the wheel with `--no-deps` imports
  `pippen` successfully, and `sys.modules` afterwards contains none of numpyro,
  jax, lightgbm, optuna, shap, nba_api, pbpstats, sklearn, typer, fastapi or
  pandera. The core install does not drag in the optional extras.
- Wheel and sdist both carry both parquet files.
- `MissingBundledDataError` is reachable and its message is accurate.
- `metric_reliability` cannot return an empty frame in place of raising.
- Every quantitative claim in ADR 0006 is exact: 5,427 rows and 227,822 bytes,
  750 rows and 42,049 bytes, 335 players, Jokić at 9.9745.
- No committed file under `docs/` exceeds the newly applied 256 KiB cap, so
  capping the two previously uncapped prefixes breaks nothing already in git.
  `tests/fixtures/` does not exist yet.
- `bash -n` passes and the `(( ))` chains in `finish` do not trip `set -e`.

---

## Still open, and not for me to close

Neither axis found a reason to hold the release. What remains needs a browser
and the maintainer's logins, and `./scripts/setup_publishing.sh` walks all of it.

- Trusted Publishing on the existing PyPI project, and the `pypi` GitHub
  environment.
- Revoking the pippen-scoped token in `.env`. Trusted Publishing adds an auth
  method rather than replacing one, so a project with both has the security of
  the weaker one.
- Replacing `AlphaNerdFx` with a legal name in `CITATION.cff` and
  `.zenodo.json` before a DOI is minted.
- The all-projects PyPI token pasted into a chat window earlier in this
  project's history. Still outstanding, and it outranks everything above.
