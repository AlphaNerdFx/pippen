# Notes

Working notes on how this workspace runs.

## Placement

`CLAUDE.md` requires this workspace to live in `docs/learning/` so the repository
root stays clean. That directory is also part of the published MkDocs site, which
has two consequences:

- Scaffolding (`MISSION.md`, `NOTES.md`, `RESOURCES.md`, `learning-records/`) is
  listed in `exclude_docs` in `mkdocs.yml` so it does not render into the public
  site. It stays in git, it just is not published.
- `lessons/` and `reference/` are HTML and are copied verbatim as static files,
  which is why they need no nav entry and why they carry their own stylesheet.

Verified 16 September 2026: `mkdocs build --strict` passes with unlisted files
present. Unlisted pages are reported at INFO level, not as a warning, so they do
not fail the strict build.

## Numbering

One sequence across the workspace, not one per directory. `0001` is the markdown
note on the data layer, `0002` is the first HTML lesson. Mixing two sequences in
one tree would put two `0001`s side by side.

## Teaching preferences observed so far

- Terms from engineering, infrastructure and MLOps get defined. Statistical terms
  do not, and defining them reads as condescension.
- Prose rules from `CLAUDE.md` apply inside lessons: no em dashes, bold reserved
  for the one thing that must not be missed, no contrast-reveal constructions, no
  filler openers.
- The uncomfortable answer goes first. That holds in a lesson as an ordering
  requirement: the consequence leads, the derivation follows.
- Lessons are built from work that was happening anyway. Detached exercises have
  not been used and should not be introduced without asking.

## Open question for the next session

`MISSION.md` was drafted from `CLAUDE.md` and the project plan rather than from
an interview. It needs confirming or correcting.
