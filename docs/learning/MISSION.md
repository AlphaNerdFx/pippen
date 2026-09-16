# Mission: Engineering practice for research code

> Drafted from `CLAUDE.md`, `docs/learning/index.md` and the project plan rather
> than from an interview. Correct anything wrong here before the next lesson,
> because every teaching decision traces back to this file.

## Why

Ship PIPPEN as real, installed, citable software, and come out of it able to
defend the engineering in a job interview rather than only the statistics. The
modelling is already a strength. The gap is everything around it: packaging,
release, filesystem guarantees, CI, and the habits that stop research code from
being unusable by anyone else.

## Success looks like

- Explaining why a published artifact is built the way it is, without notes,
  to someone who did not write it.
- Recognising a named failure mode in unfamiliar code, having only met it once
  here. Atomic writes, check-then-act, path traversal, nested cross-validation.
- Reading an unfamiliar repository's `pyproject.toml`, CI workflow and hooks and
  saying what each one guarantees.
- Shipping the next project with these practices from day one rather than
  retrofitting them.

## Constraints

- Solo, zero-dollar infrastructure budget, free tiers only.
- Learning happens inside work that was going to be done anyway. No detached
  exercises.
- Statistics, basketball analytics and modelling need no introduction.
  Engineering, infrastructure and MLOps need building from the ground.
- Lessons stay short. One tangible win each.

## Out of scope

- Statistical theory. Already strong, and re-teaching it wastes the session.
- Kubernetes beyond writing and validating manifests locally. The project runs
  on free tiers and a cluster solves no problem it has.
- Commercial ML platforms, which the project ruled out on budget and on
  explainability.
