---
name: release
description: Cut a release of the nba-impact package and its dataset. Use when the user asks to publish, tag, ship, or release a version, or to push a new dataset artifact.
---

# Cut a release

## Before tagging anything

```bash
make check        # lint, types, tests
make docs         # strict docs build
uv build          # sdist and wheel
uvx twine check dist/*
```

All four must pass. Continuous integration runs the same commands, so a failure
here is a failure there.

## Version numbers

Versions come from Conventional Commit messages, not from judgment:

| Commits since last release | Bump |
|---|---|
| any `feat:` | minor |
| only `fix:` | patch |
| any `!` or `BREAKING CHANGE:` | major |

While the project is below 1.0, a breaking change bumps the minor version.

## A scientific release is different from a software release

If published numbers changed, the release notes must state:

- which metric changed and by how much, on a fixed reference season;
- what caused the change: new data, a method change, or a bug fix;
- whether previously published values should be considered wrong.

A metric that changes without explanation is a metric nobody can build on. This
matters more than the changelog entry.

## Steps

1. Update `CHANGELOG.md` under `Unreleased`, then move it under the new version.
2. Commit: `chore(release): v0.2.0`.
3. Tag: `git tag -a v0.2.0 -m "v0.2.0"`.
4. Push the tag: `git push origin v0.2.0`.
5. The release workflow builds, publishes to PyPI through Trusted Publishing, and
   attaches artifacts to the GitHub release.

## Dataset releases

Dataset artifacts are versioned separately, tagged `data-vN`. Each must ship with:

- the CC BY 4.0 licence file;
- attribution to hoopR and pbpstats;
- the schema and the seasons covered;
- the commit that produced it, so it can be regenerated.

## Never

- Never publish with an API token. Trusted Publishing is configured; use it.
- Never tag from a dirty working tree.
- Never publish a dataset containing values the licensing table forbids.
