# Contributing to pippen

Thanks for considering a contribution. This document tells you how to set up,
what the project expects, and how changes get reviewed.

## Ground rules

- Be civil. The [Code of Conduct](CODE_OF_CONDUCT.md) applies everywhere in this
  project, including issues and pull requests.
- Open an issue before starting significant work, so effort is not wasted on
  something already in progress or out of scope.
- **Never commit data.** `data/` is gitignored for a reason. Data is published
  through releases, not through git history.
- **Never add a paywalled or unlicensed value to a published artifact.** See the
  data licensing table in the README. This is the one rule with no exceptions.

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for environments and locking.

```bash
git clone https://github.com/AlphaNerdFx/pippen
cd pippen
uv sync --extra dev
uv run pre-commit install
```

`pre-commit install` registers hooks that run on every commit. They catch the
same problems continuous integration would, but seconds after you write the code
rather than minutes after you push it.

## The checks

Everything below runs in continuous integration and must pass before merge.

```bash
make lint        # ruff check + ruff format --check
make typecheck   # mypy, strict mode
make test        # pytest with coverage
make check       # all three
```

Notes on each:

- **ruff** replaces Black, isort and Flake8. `make format` fixes what it can.
- **mypy runs in strict mode.** New code needs type annotations. If a third-party
  library has no stubs, add it to the override list in `pyproject.toml` rather
  than sprinkling `# type: ignore`.
- **Tests use pytest.** Anything touching the possession parser should also get a
  property-based test with Hypothesis, because that code has invariants that hold
  for every game: possessions reconcile to the box score, every stint has five
  players a side, and results do not depend on player ordering.

Tests that need the network must be marked:

```python
@pytest.mark.network
def test_downloads_a_season() -> None: ...
```

CI runs `-m "not network"` by default so the suite stays fast and offline-safe.

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/).
The release tooling reads them to decide version numbers and to write the
changelog, so the prefix is not decoration.

```
feat(rapm): add bootstrap standard errors to the ridge solver
fix(data): handle period-boundary substitutions missing from ESPN feeds
docs: explain why DBPM is excluded
chore(deps): bump pandera to 0.21
```

`feat` raises the minor version. `fix` raises the patch version. A `!` after the
scope, or a `BREAKING CHANGE:` footer, raises the major version.

## Pull requests

1. Branch from `main`.
2. Keep the change focused. One concern per pull request.
3. Make sure `make check` passes locally.
4. Describe what changed and why. If it changes a number the project publishes,
   say by how much.

## Scientific changes

If your change alters a published metric, the pull request must include:

- what the number was before and after, on a fixed reference season;
- why the new number is more correct, not merely different;
- an updated entry in `docs/methodology/` if the method itself changed.

A metric that changes silently between versions is not a metric anyone can build
on.

## Dependency updates

Dependabot's automated pull requests are deliberately switched off, so every
commit here has a human author. Dependabot **security alerts** remain enabled:
they notify without committing anything.

Update dependencies yourself, monthly:

```bash
make upgrade      # uv lock --upgrade, resync, regenerate requirements.txt
make check        # confirm nothing broke
```

Then commit the lockfile diff like any other change.

## Reporting a security issue

Do not open a public issue. See [SECURITY.md](SECURITY.md).
