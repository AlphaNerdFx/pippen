# Handoff

State of PIPPEN for whoever picks it up next, human or model.

Written 22 September 2026, at `b48ad30`. This file replaces `.context/HANDOVER.md`,
which had gone stale by six phases and is now a pointer here. One live handoff
document, because two documents with one job is how the first one went stale.

## The single most important fact

**45 commits are unpushed and no CI runner has seen any of them.** The last CI
run was 14 September at `904828c4`. Everything from Phase 3 closeout onward,
which is Phases 3, 4, 5, 6, 7 and most of 8, exists only on one machine. The
release workflow that Trusted Publishing depends on has never executed.

Nothing is tagged. `v1.0.0` is committed but not tagged and not pushed, on
instruction.

## Where things stand

Version 1.0.0, committed at `bbc4a91`, with one substantive change after it.

| | |
|---|---|
| Tests | 560 passing, 35 deselected as slow |
| Types | mypy strict clean over 73 files |
| Docs | `mkdocs build --strict` clean |
| Artifacts | wheel and sdist both pass `twine check` |
| Source | 36 modules under `src/pippen/` |
| Decisions | 7 ADRs in `docs/architecture/decisions/` |

Phases 0 through 7 are complete or complete-except-manual. Phase 8 is partly
done. `TODO.md` is the roadmap and carries the amended done-when clauses; read
it rather than trusting this table for detail.

The central claim was tested and the answer is no. Fusing public metrics does
not beat RAPM alone and is not distinguishable from it (p = 0.171). That result
is published rather than buried, in `docs/methodology/claim-under-test.md`.

## What is left, and who can do it

### Blocked on the maintainer, no CLI route exists

These are the only real blockers. Each was checked for an automatable path and
none has one.

1. **PyPI Trusted Publishing.** `https://pypi.org/manage/project/pippen/settings/publishing/`
   with owner `AlphaNerdFx`, repository `pippen`, workflow `release.yml`,
   environment `pypi`. PyPI's own documentation describes only the browser flow
   and references no API. The GitHub half is already done: the `pypi`
   environment exists with the maintainer as required reviewer, created through
   `gh`.
2. **Revoke `PYPI_TOKEN`.** It is still live in the gitignored `.env`. Trusted
   Publishing adds a second door rather than closing the first, so until this is
   revoked the project has the security of the weaker credential. This has been
   outstanding for the whole session.
3. **Revoke the all-projects PyPI token** that was pasted into a chat window
   earlier in this project's history. Longest-outstanding item in the project.
4. **Zenodo.** `https://zenodo.org/account/settings/github/`, toggle on before
   tagging, because Zenodo only archives releases created after the toggle.
5. **Replace `AlphaNerdFx` with a legal name** in `CITATION.cff` and
   `.zenodo.json` before any DOI is minted. A citation carrying a handle is hard
   to credit academically.
6. **Hugging Face Spaces deploy.** Needs an HF token that is not set. The
   `huggingface-cli` and `hf` binaries are installed.

`./scripts/setup_publishing.sh` walks 1, 2, 4 and the tag. It is resumable
through markers in `.env` and refuses to tag a dirty tree or a non-main branch.

### Blocked by a recorded architectural decision

**Scheduled retrain and publish.** ADR 0006 puts a rebuild of the shipped tables
at hours of rate-limited downloading, which a CI runner cannot complete. A
scheduled job that cannot finish its own task would be automation theatre. This
is recorded as not-doing rather than not-done.

### Open and doable

- **Method write-up** (`TODO.md` Phase 8). The material largely exists across
  `docs/methodology/`. What is missing is a single narrative entry point that
  takes a reader from problem to negative result. `docs/methodology/limitations.md`
  was rewritten today and is accurate.
- **Post to r/nbaanalytics and the APBRmetrics forum.** Judgement, not code.
- **Consider a JOSS submission.** Would need a `paper.md`.

## Known defects, all found by building on them

None of these are speculative. Each was surfaced by something downstream
depending on it.

| Defect | Where | Status |
|---|---|---|
| 3 of 5,427 rating rows have a null player name | ESPN to NBA crosswalk, ids 2882 and 204058 | Open, documented in the model card and changelog. All three under 20 possessions |
| No per-metric correlation against RAPM ships | `metric_reliability.parquet` | Open. The -0.564 finding is stated rather than plotted because charting it would mean inventing the x-axis |
| Core dependencies far exceed what the public API needs | `pyproject.toml` | Open and deliberate. `import pippen` needs pandas and pyarrow; scipy, scikit-learn, pandera, typer and rich are core. 588 MB of a 939 MB image. Narrowing it is breaking and now costs a major bump |
| Nothing regenerates the shipped tables | `src/pippen/_data/` | Open. They were written ad-hoc in `a349182`. `scripts/add_tenure_columns.py` augments but does not generate |

## The failure mode this project keeps hitting

Worth reading before changing anything, because it has produced five defects in
one session.

A claim is written in one artifact. Its referent lives in another and changes
independently. Nothing consults both. The claim goes false silently.

Instances: `limitations.md` said "Nothing is validated yet" after everything was
validated, and promised an interval that ADR 0007 records withdrawing. The
wizard matched `^PYPI_TOKEN=` against a file written `PYPI_TOKEN = `. The test
suite needed an extra CI does not install. `CLAUDE.md` asserted a knowledge
graph existed before it did. A packaging lesson told a reader to verify a file
at 227,822 bytes, and an unrelated change made it 235,428 within hours.

**Defences that work, in order:** delete the second copy, generate it rather
than commit it, assert it in a test, and only then review it. Review is last
because review examines what changed, and this defect lives in what did not.

Worked examples already in the repository:
`tests/unit/test_api.py::test_no_rating_response_carries_an_interval` makes ADR
0007 enforceable. `scripts/gen_drift.py` renders a page at build time so no
committed copy can go stale. `pyproject.toml` reads the version from
`__init__.py` so they cannot disagree.

## Running it

```bash
uv sync --all-extras
uv run pytest -q -m "not slow"        # 560 tests
uv run pippen --help                   # 13 commands
uv run uvicorn pippen.api.app:app      # http://localhost:8000/docs
uv run streamlit run dashboard/app.py  # http://localhost:8501
docker build -f deploy/Dockerfile -t pippen:1.0.0 .
```

`make check` runs lint, types and tests. `make docs` builds strictly.

Note that `uv sync --extra dev` alone leaves three tests skipping, because they
need `nba_api` from the `sources` extra. That is by design now, via
`importorskip`, rather than the failure it used to be.

## Where the reasoning lives

Do not re-derive these. They are written down.

- `TODO.md` is the roadmap, outcome-gated, with amended done-when clauses.
- `docs/architecture/decisions/` holds 7 ADRs. 0003 through 0007 are the ones
  that constrain day-to-day work.
- `docs/methodology/` holds the measurement write-ups, including the claim under
  test and the corrected limitations page.
- `docs/model-card.md` states intended use and what is out of scope.
- `.context/reviews/` holds two closeout reviews. These are dated records of
  what was true then. Do not edit them to match the present.
- `CLAUDE.md` holds the writing, explanation and orchestration rules, and they
  are enforced in review.
- `docs/learning/` is the teaching workspace. `MISSION.md` there was drafted
  from evidence rather than an interview and still needs confirming.

## Suggested skills for the next agent

| Skill | When |
|---|---|
| `/grilling` | Before building anything non-trivial. Required by `CLAUDE.md` |
| `/professor` | The moment a named technique enters the code |
| `/code-review` | On every change before committing, two axes |
| `/ponytail:ponytail-review` | On any diff that adds a dependency or an abstraction |
| `/release` | When the manual publishing steps above are finally cleared |
| `/refresh-data` | If a new season needs ingesting |

`/teach` and `/handoff` carry `disable-model-invocation: true` and can only be
started by the maintainer typing them.

## What the next session should probably do first

Push. 45 commits have never been validated by anything but one laptop, and
every hour that continues raises the cost of whatever CI finds.
